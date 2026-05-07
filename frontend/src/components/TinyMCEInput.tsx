/**
 * MonacoHtmlInput — Full HTML code editor bridged into React Admin's form system.
 *
 * Uses Monaco Editor (VS Code's engine) to edit complete HTML email templates,
 * including <!DOCTYPE>, <head>, <style>, and Django template syntax.
 * Zero content stripping — what you paste is what gets saved.
 *
 * The old TinyMCEInput is replaced by this component. The export name
 * TinyMCEInput is kept as an alias so no other import sites need updating.
 */
import MonacoEditor from '@monaco-editor/react';
import { useInput, type InputProps } from 'react-admin';
import { FormControl, FormHelperText, FormLabel, Box } from '@mui/material';

export interface TinyMCEInputProps extends InputProps {
  /** Editor height in pixels. Defaults to 500. */
  height?: number;
}

export const TinyMCEInput = ({ height = 500, label, ...props }: TinyMCEInputProps) => {
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
          '&:focus-within': { borderColor: 'primary.main' },
        }}
      >
        <MonacoEditor
          height={height}
          language="html"
          theme="vs-dark"
          value={field.value ?? ''}
          onChange={(value) => field.onChange(value ?? '')}
          onMount={(editor) => {
            // Propagate blur so react-hook-form marks the field as touched
            editor.onDidBlurEditorWidget(() => field.onBlur());
          }}
          options={{
            minimap: { enabled: false },
            wordWrap: 'on',
            fontSize: 13,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
          }}
        />
      </Box>
      {fieldState.error && (
        <FormHelperText>{fieldState.error.message}</FormHelperText>
      )}
    </FormControl>
  );
};
