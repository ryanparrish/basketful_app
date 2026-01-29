# apps/voucher/views_reports.py
"""Views for voucher reports."""
from datetime import date, timedelta
from io import BytesIO
from decimal import Decimal
from collections import defaultdict

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from apps.lifeskills.models import Program
from apps.voucher.forms import VoucherRedemptionReportForm
from apps.voucher.models import Voucher, OrderVoucher


def _get_date_range(date_range_choice: str, start_date=None, end_date=None):
    """
    Calculate start and end dates based on date range choice.
    
    Args:
        date_range_choice: One of 'this_week', 'this_month', 'last_month', 'this_year', 'custom'
        start_date: Custom start date (only used if date_range_choice is 'custom')
        end_date: Custom end date (only used if date_range_choice is 'custom')
        
    Returns:
        Tuple of (start_date, end_date) as date objects
    """
    today = date.today()
    
    if date_range_choice == 'this_week':
        # Start from Monday of current week
        start_of_week = today - timedelta(days=today.weekday())
        return start_of_week, today
    elif date_range_choice == 'this_month':
        # First day of current month to today
        return today.replace(day=1), today
    elif date_range_choice == 'last_month':
        # Get first and last day of previous month
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_of_last_month.replace(day=1)
        return first_of_last_month, last_of_last_month
    elif date_range_choice == 'this_year':
        # Jan 1 of current year to today
        return date(today.year, 1, 1), today
    elif date_range_choice == 'custom':
        return start_date, end_date
    else:
        # Default to this month
        return today.replace(day=1), today


def _get_redemption_data(start_date, end_date, program=None, voucher_type=None, group_by='program'):
    """
    Get voucher redemption data for the given date range.
    
    Uses OrderVoucher.applied_at for precise redemption date, with fallback
    to Voucher.updated_at for consumed vouchers without OrderVoucher records.
    
    Args:
        start_date: Start date for filtering
        end_date: End date for filtering
        program: Optional Program instance to filter by
        voucher_type: Optional voucher type ('grocery' or 'life')
        group_by: How to group results ('program' or 'participant')
        
    Returns:
        Dict with aggregated data grouped by program or participant
    """
    # Convert dates to datetime for timezone-aware comparison
    start_datetime = timezone.make_aware(
        timezone.datetime.combine(start_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(end_date, timezone.datetime.max.time())
    )
    
    # Get vouchers redeemed via OrderVoucher
    order_voucher_qs = OrderVoucher.objects.filter(
        applied_at__gte=start_datetime,
        applied_at__lte=end_datetime,
        voucher__state=Voucher.CONSUMED
    ).select_related(
        'voucher__account__participant__program',
        'voucher'
    )
    
    # Get consumed vouchers that may not have OrderVoucher records
    # (fallback using updated_at)
    consumed_vouchers_qs = Voucher.objects.filter(
        state=Voucher.CONSUMED,
        updated_at__gte=start_datetime,
        updated_at__lte=end_datetime
    ).select_related(
        'account__participant__program'
    )
    
    # Apply program filter
    if program:
        order_voucher_qs = order_voucher_qs.filter(
            voucher__account__participant__program=program
        )
        consumed_vouchers_qs = consumed_vouchers_qs.filter(
            account__participant__program=program
        )
    
    # Apply voucher type filter
    if voucher_type:
        order_voucher_qs = order_voucher_qs.filter(
            voucher__voucher_type=voucher_type
        )
        consumed_vouchers_qs = consumed_vouchers_qs.filter(
            voucher_type=voucher_type
        )
    
    # Aggregate data by program or participant
    result_data = defaultdict(lambda: {
        'voucher_count': 0,
        'total_amount': Decimal('0.00'),
        'grocery_count': 0,
        'life_count': 0,
        'voucher_ids': set(),
        'program_name': '',
    })
    
    # Process OrderVoucher records (primary source)
    for ov in order_voucher_qs:
        voucher = ov.voucher
        participant = voucher.account.participant
        
        if group_by == 'participant':
            key = f"{participant.customer_number} - {participant.name}"
            result_data[key]['program_name'] = participant.program.name
        else:
            key = participant.program.name
            
        if voucher.pk in result_data[key]['voucher_ids']:
            continue  # Skip duplicates
            
        result_data[key]['voucher_ids'].add(voucher.pk)
        result_data[key]['voucher_count'] += 1
        result_data[key]['total_amount'] += ov.applied_amount
        
        if voucher.voucher_type == 'grocery':
            result_data[key]['grocery_count'] += 1
        else:
            result_data[key]['life_count'] += 1
    
    # Process consumed vouchers not in OrderVoucher (fallback)
    for voucher in consumed_vouchers_qs:
        participant = voucher.account.participant
        
        if group_by == 'participant':
            key = f"{participant.customer_number} - {participant.name}"
            result_data[key]['program_name'] = participant.program.name
        else:
            key = participant.program.name
            
        # Check if we already counted this voucher via OrderVoucher
        if voucher.pk in result_data[key]['voucher_ids']:
            continue
            
        result_data[key]['voucher_ids'].add(voucher.pk)
        result_data[key]['voucher_count'] += 1
        result_data[key]['total_amount'] += voucher.voucher_amnt
        
        if voucher.voucher_type == 'grocery':
            result_data[key]['grocery_count'] += 1
        else:
            result_data[key]['life_count'] += 1
    
    # Clean up voucher_ids from output (not needed in final data)
    result = {}
    for key, data in result_data.items():
        result[key] = {
            'voucher_count': data['voucher_count'],
            'total_amount': data['total_amount'],
            'grocery_count': data['grocery_count'],
            'life_count': data['life_count'],
            'program_name': data.get('program_name', ''),
        }
    
    return result


@staff_member_required
def voucher_redemption_report(request):
    """
    View for voucher redemption report.
    
    Shows voucher redemption counts grouped by program or participant for a selected time period.
    """
    form = VoucherRedemptionReportForm(request.GET or None)
    report_data = None
    totals = None
    date_range_display = None
    group_by = 'program'
    
    if request.GET and form.is_valid():
        date_range_choice = form.cleaned_data['date_range']
        start_date, end_date = _get_date_range(
            date_range_choice,
            form.cleaned_data.get('start_date'),
            form.cleaned_data.get('end_date')
        )
        
        program = form.cleaned_data.get('program')
        voucher_type = form.cleaned_data.get('voucher_type')
        group_by = form.cleaned_data.get('group_by', 'program')
        
        report_data = _get_redemption_data(
            start_date, end_date, program, voucher_type, group_by
        )
        
        # Calculate totals
        totals = {
            'voucher_count': sum(d['voucher_count'] for d in report_data.values()),
            'total_amount': sum(d['total_amount'] for d in report_data.values()),
            'grocery_count': sum(d['grocery_count'] for d in report_data.values()),
            'life_count': sum(d['life_count'] for d in report_data.values()),
        }
        
        date_range_display = f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"
        
        # Handle PDF export
        if 'export_pdf' in request.GET:
            return _generate_pdf_report(
                report_data, totals, date_range_display, program, voucher_type, group_by
            )
    
    context = {
        'form': form,
        'report_data': report_data,
        'totals': totals,
        'date_range_display': date_range_display,
        'group_by': group_by,
        'title': 'Voucher Redemption Report',
    }
    
    return render(
        request,
        'admin/voucher/redemption_report.html',
        context
    )


def _generate_pdf_report(report_data, totals, date_range_display, program=None, voucher_type=None, group_by='program'):
    """
    Generate PDF version of the redemption report.
    
    Args:
        report_data: Dict of program/participant data
        totals: Dict with total counts and amounts
        date_range_display: Formatted date range string
        program: Optional filtered program
        voucher_type: Optional filtered voucher type
        group_by: How data is grouped ('program' or 'participant')
        
    Returns:
        HttpResponse with PDF attachment
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=12,
        alignment=1  # Center
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=6,
        alignment=1  # Center
    )
    
    # Title
    elements.append(Paragraph("Voucher Redemption Report", title_style))
    elements.append(Paragraph(f"Period: {date_range_display}", subtitle_style))
    
    # Filters applied
    filters = []
    if program:
        filters.append(f"Program: {program.name}")
    if voucher_type:
        filters.append(f"Type: {voucher_type.title()}")
    if filters:
        elements.append(Paragraph(f"Filters: {', '.join(filters)}", subtitle_style))
    
    elements.append(Spacer(1, 0.25 * inch))
    
    # Summary totals
    summary_data = [
        ['Total Vouchers Redeemed', str(totals['voucher_count'])],
        ['Total Amount', f"${totals['total_amount']:.2f}"],
        ['Grocery Vouchers', str(totals['grocery_count'])],
        ['Life Vouchers', str(totals['life_count'])],
    ]
    
    summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.25 * inch))
    
    # Detail by program or participant
    if report_data:
        if group_by == 'participant':
            elements.append(Paragraph("Breakdown by Participant", styles['Heading2']))
            elements.append(Spacer(1, 0.1 * inch))
            
            detail_data = [['Participant', 'Program', 'Vouchers', 'Grocery', 'Life', 'Amount']]
            
            for participant_name, data in sorted(report_data.items()):
                detail_data.append([
                    participant_name,
                    data.get('program_name', ''),
                    str(data['voucher_count']),
                    str(data['grocery_count']),
                    str(data['life_count']),
                    f"${data['total_amount']:.2f}"
                ])
            
            # Add totals row
            detail_data.append([
                'TOTAL',
                '',
                str(totals['voucher_count']),
                str(totals['grocery_count']),
                str(totals['life_count']),
                f"${totals['total_amount']:.2f}"
            ])
            
            detail_table = Table(
                detail_data,
                colWidths=[2 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 1 * inch]
            )
        else:
            elements.append(Paragraph("Breakdown by Program", styles['Heading2']))
            elements.append(Spacer(1, 0.1 * inch))
            
            detail_data = [['Program', 'Vouchers', 'Grocery', 'Life', 'Amount']]
            
            for program_name, data in sorted(report_data.items()):
                detail_data.append([
                    program_name,
                    str(data['voucher_count']),
                    str(data['grocery_count']),
                    str(data['life_count']),
                    f"${data['total_amount']:.2f}"
                ])
            
            # Add totals row
            detail_data.append([
                'TOTAL',
                str(totals['voucher_count']),
                str(totals['grocery_count']),
                str(totals['life_count']),
                f"${totals['total_amount']:.2f}"
            ])
            
            detail_table = Table(
                detail_data, 
                colWidths=[2.5 * inch, 1 * inch, 1 * inch, 1 * inch, 1.5 * inch]
            )
        detail_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#336699')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Data rows
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            # Totals row
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f5f5f5')]),
        ]))
        elements.append(detail_table)
    else:
        elements.append(Paragraph(
            "No redemption data found for the selected period.",
            styles['Normal']
        ))
    
    # Footer
    elements.append(Spacer(1, 0.5 * inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey
    )
    elements.append(Paragraph(
        f"Generated on {date.today().strftime('%B %d, %Y')}",
        footer_style
    ))
    
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="voucher_redemption_report_{date.today()}.pdf"'
    return response
