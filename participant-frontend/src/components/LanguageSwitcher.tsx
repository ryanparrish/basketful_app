/**
 * Language Switcher
 * - variant="menu": globe icon button with a dropdown (header)
 * - variant="select": labelled select field (login page, account page)
 * Language names are always shown in their own language.
 */
import React, { useState } from 'react';
import {
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  FormControl,
  InputLabel,
  Select,
  Tooltip,
} from '@mui/material';
import { Language as LanguageIcon, Check as CheckIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGUAGES } from '../i18n/languages';
import { useLanguagePreference } from '../shared/hooks/useLanguagePreference';

interface LanguageSwitcherProps {
  variant: 'menu' | 'select';
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({ variant }) => {
  const { t } = useTranslation();
  const { currentLanguage, changeLanguage } = useLanguagePreference();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  // i18next may report a regional code (e.g. "es-MX"); match on the base
  const baseLanguage = currentLanguage?.split('-')[0];

  if (variant === 'select') {
    return (
      <FormControl size="small" fullWidth>
        <InputLabel id="language-select-label">{t('language.label')}</InputLabel>
        <Select
          labelId="language-select-label"
          value={baseLanguage}
          label={t('language.label')}
          onChange={(event) => changeLanguage(event.target.value)}
          inputProps={{ 'aria-label': t('language.select') }}
        >
          {SUPPORTED_LANGUAGES.map((language) => (
            <MenuItem key={language.code} value={language.code}>
              {language.nativeName}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    );
  }

  return (
    <>
      <Tooltip title={t('language.select')}>
        <IconButton
          color="inherit"
          onClick={(event) => setAnchorEl(event.currentTarget)}
          aria-label={t('language.select')}
        >
          <LanguageIcon />
        </IconButton>
      </Tooltip>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <MenuItem
            key={language.code}
            selected={language.code === baseLanguage}
            onClick={() => {
              setAnchorEl(null);
              changeLanguage(language.code);
            }}
          >
            {language.code === baseLanguage && (
              <ListItemIcon>
                <CheckIcon fontSize="small" />
              </ListItemIcon>
            )}
            {language.nativeName}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
};

export default LanguageSwitcher;
