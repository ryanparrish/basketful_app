# apps/voucher/views.py
"""Views for bulk voucher creation in Django Admin."""
import logging
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from apps.lifeskills.models import Program
from apps.account.models import Participant, AccountBalance
from apps.voucher.models import Voucher
from apps.voucher.forms import BulkVoucherConfigurationForm, BulkVoucherConfirmationForm

logger = logging.getLogger(__name__)


@staff_member_required
def bulk_voucher_configure(request):
    """Step 1: Configuration form for bulk voucher creation."""
    if request.method == 'POST':
        form = BulkVoucherConfigurationForm(request.POST)
        if form.is_valid():
            # Store configuration in session
            request.session['bulk_voucher_config'] = {
                'program_id': form.cleaned_data['program'].id,
                'voucher_type': form.cleaned_data['voucher_type'],
                'vouchers_per_participant': form.cleaned_data['vouchers_per_participant'],
                'notes': form.cleaned_data['notes'],
            }
            return redirect('admin:bulk_voucher_preview')
    else:
        form = BulkVoucherConfigurationForm()
    
    context = {
        'form': form,
        'title': 'Bulk Voucher Creation - Configuration',
        'site_header': 'Django Administration',
        'has_permission': True,
    }
    return render(request, 'admin/voucher/bulk_voucher_configure.html', context)


@staff_member_required
def bulk_voucher_preview(request):
    """Step 2: Preview participants and confirm creation."""
    config = request.session.get('bulk_voucher_config')
    
    if not config:
        messages.error(request, "Configuration not found. Please start over.")
        return redirect('admin:bulk_voucher_configure')
    
    program = get_object_or_404(Program, id=config['program_id'])
    participants = Participant.objects.filter(program=program, active=True)
    
    # Prepare participant list with account info
    participant_list = []
    participants_without_account = []
    
    for participant in participants:
        try:
            account = AccountBalance.objects.get(participant=participant)
            participant_list.append({
                'participant': participant,
                'account': account,
                'has_account': True,
            })
        except AccountBalance.DoesNotExist:
            participants_without_account.append(participant)
            participant_list.append({
                'participant': participant,
                'account': None,
                'has_account': False,
            })
    
    if request.method == 'POST':
        # Get selected participant IDs from form
        selected_ids = request.POST.getlist('selected_participants')
        if selected_ids:
            # Store selected participant IDs in session
            config['selected_participant_ids'] = [int(pid) for pid in selected_ids]
            request.session['bulk_voucher_config'] = config
            request.session.modified = True
            
            form = BulkVoucherConfirmationForm(request.POST)
            if form.is_valid():
                # Proceed to creation
                return redirect('admin:bulk_voucher_create')
        else:
            messages.error(request, "Please select at least one participant.")
            form = BulkVoucherConfirmationForm(request.POST)
    else:
        form = BulkVoucherConfirmationForm(initial={
            'program_id': config['program_id'],
            'voucher_type': config['voucher_type'],
            'vouchers_per_participant': config['vouchers_per_participant'],
            'notes': config['notes'],
        })
    
    # Calculate totals based on all participants (will be recalculated at creation time)
    total_participants = len([p for p in participant_list if p['has_account']])
    total_vouchers = total_participants * config['vouchers_per_participant']
    
    context = {
        'form': form,
        'program': program,
        'participant_list': participant_list,
        'total_participants': total_participants,
        'total_vouchers': total_vouchers,
        'vouchers_per_participant': config['vouchers_per_participant'],
        'voucher_type': config['voucher_type'],
        'notes': config['notes'],
        'participants_without_account': participants_without_account,
        'title': 'Bulk Voucher Creation - Preview',
        'site_header': 'Django Administration',
        'has_permission': True,
    }
    return render(request, 'admin/voucher/bulk_voucher_preview.html', context)


@staff_member_required
def bulk_voucher_create(request):
    """Step 3: Execute bulk voucher creation with validation."""
    config = request.session.get('bulk_voucher_config')
    
    if not config:
        messages.error(request, "Configuration not found. Please start over.")
        return redirect('admin:bulk_voucher_configure')
    
    program = get_object_or_404(Program, id=config['program_id'])
    
    # Get selected participant IDs from config (set in preview step)
    selected_ids = config.get('selected_participant_ids', [])
    if selected_ids:
        participants = Participant.objects.filter(id__in=selected_ids, program=program, active=True)
    else:
        # Fallback to all participants if no selection was made
        participants = Participant.objects.filter(program=program, active=True)
    
    created_count = 0
    skipped_participants = []
    error_messages = []
    
    try:
        with transaction.atomic():
            for participant in participants:
                try:
                    # Get or skip if no account
                    try:
                        account = AccountBalance.objects.get(participant=participant)
                    except AccountBalance.DoesNotExist:
                        skipped_participants.append(participant)
                        error_messages.append(
                            f"{participant.name} (#{participant.customer_number or participant.id}): "
                            "No account balance found"
                        )
                        continue
                    
                    # Create vouchers for this participant
                    for _ in range(config['vouchers_per_participant']):
                        voucher = Voucher(
                            account=account,
                            voucher_type=config['voucher_type'],
                            notes=config['notes'] or f"Bulk created for program: {program.name}",
                            state=Voucher.PENDING,
                            active=True,
                        )
                        
                        try:
                            # Run model validation
                            voucher.full_clean()
                            voucher.save()
                            created_count += 1
                        except ValidationError as e:
                            skipped_participants.append(participant)
                            error_messages.append(
                                f"{participant.name} (#{participant.customer_number or participant.id}): "
                                f"Validation error - {', '.join(e.messages)}"
                            )
                            # Break inner loop, don't create more vouchers for this participant
                            break
                
                except Exception as e:
                    skipped_participants.append(participant)
                    error_messages.append(
                        f"{participant.name} (#{participant.customer_number or participant.id}): "
                        f"Unexpected error - {str(e)}"
                    )
                    logger.exception("Error creating vouchers for participant %s", participant.id)
                    continue
        
        # Clear session config
        del request.session['bulk_voucher_config']
        
        # Show results
        if created_count > 0:
            messages.success(
                request,
                f"Successfully created {created_count} voucher(s) for program '{program.name}'."
            )
        
        if skipped_participants:
            unique_skipped = list(set(skipped_participants))
            messages.warning(
                request,
                f"{len(unique_skipped)} participant(s) were skipped due to validation or account errors. "
                "Check the details below."
            )
            
            # Add detailed error messages
            for error_msg in error_messages:
                messages.warning(request, f"• {error_msg}")
        
        return redirect('admin:voucher_voucher_changelist')
    
    except Exception as e:
        messages.error(
            request,
            f"An unexpected error occurred during bulk creation: {str(e)}"
        )
        logger.exception("Fatal error during bulk voucher creation")
        return redirect('admin:bulk_voucher_configure')
