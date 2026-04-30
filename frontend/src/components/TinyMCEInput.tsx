/**
 * TinyMCEInput — WYSIWYG HTML editor bridged into React Admin's form system.
 *
 * Reuses the TinyMCE bundle already served by django-tinymce at /static/tinymce/
 * — no CDN key, no extra assets to deploy. The component is a drop-in replacement
 * for <TextInput multiline> anywhere html_content (or any HTML string field) is edited.
 */
import { Editor } from '@tinymce/tinymce-react';
import { useInput, type InputProps } from 'react-admin';
import { FormControl, FormHelperText, FormLabel, Box } from '@mui/material';

export interface TinyMCEInputProps extends InputProps {
  /** Editor height in pixels. Defaults to 450. */
  height?: number;
}

export const TinyMCEInput = ({ height = 450, label, ...props }: TinyMCEInputProps) => {
  const { field, fieldState, isRequired } = useInput(props);

  return (
    <FormControl fullWidth error={!!fieldState.error} sx={{ my: 1 }}>
      {label !== false && (
        <FormLabel required={isRequired} sx={{ mb: 0.5, fontSize: '0.75rem', color: 'text.secondary' }}>
          {label ?? props.source}
        </FormLabel>
      )}
      <Box
        sx={{
          border: '1px solid',
          borderColor: fieldState.error ? 'error.main' : 'grey.400',
          borderRadius: 1,
          overflow: 'hidden',
          '&:focus-within': { borderColor: 'primary.main', borderWidth: 2 },
        }}
      >
        <Editor
          tinymceScriptSrc="/static/tinymce/tinymce.min.js"
          value={field.value ?? ''}
          onEditorChange={(content: string) => field.onChange(content)}
          onBlur={field.onBlur}
          init={{
            height,
            menubar: false,
            branding: false,
            resize: false,
            plugins: ['link', 'lists', 'code', 'table', 'image', 'preview'],
            toolbar:
              'bold italic underline | forecolor | ' +
              'bullist numlist | link | table | ' +
              'code preview',
            content_style:
              'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; }',
            // Prevent inline styles that break email clients
            valid_styles: {
              '*': 'color,font-weight,font-style,text-decoration,text-align',
            },
          }}
        />
      </Box>
      {fieldState.error && (
        <FormHelperText>{fieldState.error.message}</FormHelperText>
      )}
    </FormControl>
  );
};
