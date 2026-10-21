import React from 'react';
import { useTranslation } from 'react-i18next';
import { esES as materialEs, zhCN as materialZh } from '@mui/material/locale';
import { esES as pickerEs, zhCN as pickerZh } from '@mui/x-date-pickers/locales';
import { createRoot } from 'react-dom/client';
import Fade from '@mui/material/Fade';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterMoment } from '@mui/x-date-pickers/AdapterMoment';
import { HashRouter } from 'react-router-dom';
import { ThemeProvider, StyledEngineProvider, createTheme } from '@mui/material/styles';
import App from './components/app/App';
import LayoutContext from './components/app/LayoutContext';
import './index.scss';
import { COLORS } from './common/colors';
import './i18n/config';

const theme = createTheme();
const v5Theme = createTheme(theme, {
  palette: {
    ...COLORS,
    success: {
      ...COLORS.primary
    },
    info: {
      ...COLORS.secondary
    },
    surface: {
      ...COLORS.surface
    },
    neutral: {
      ...COLORS.neutral
    },
    "default": {
      light: COLORS.secondary['40']
    },
  },
  components: {
    MuiTooltip: {
      defaultProps: {
        arrow: true,
        leaveDelay: 300,
        slots: {
          transition: Fade,
        },
        slotProps: {
          transition: { timeout: 300 },
        }
      }
    },
    MuiTextField: {
      defaultProps: {
        size: 'small'
      },
      styleOverrides: {
        root: {
          background: COLORS.primary.contrastText,
        },
      },
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: {
          color: COLORS.surface.contrastText
        }
      }
    },
    MuiTab: {
      styleOverrides: {
        root: {
          color: COLORS.surface.contrastText
        }
      }
    },
    MuiButton: {
      variants: [
        {
          props: { variant: "contained", color: COLORS.surface.n96 },
          style: {
            color: theme.palette.getContrastText(COLORS.surface.n96)
          }
        },
        {
          props: { variant: "outlined", color: COLORS.surface.n96 },
          style: {
            color: theme.palette.text.primary,
            borderColor:
                    theme.palette.mode === "light"
                    ? "rgba(0, 0, 0, 0.23)"
                    : "rgba(255, 255, 255, 0.23)",
            "&.Mui-disabled": {
              border: `1px solid ${theme.palette.action.disabledBackground}`
            },
            "&:hover": {
              borderColor:
                      theme.palette.mode === "light"
                      ? "rgba(0, 0, 0, 0.23)"
                      : "rgba(255, 255, 255, 0.23)",
              backgroundColor: theme.alpha(theme.palette.text.primary, theme.palette.action.hoverOpacity)
            }
          }
        },
        {
          props: { color: COLORS.surface.contrastText, variant: "text" },
          style: {
            color: theme.palette.text.primary,
            "&:hover": {
              backgroundColor: theme.alpha(theme.palette.text.primary, theme.palette.action.hoverOpacity)
            }
          }
        },
        {
          props: { variant: "contained", color: "default" },
          style: {
            backgroundColor: COLORS.surface.n96,
            color: theme.palette.getContrastText(COLORS.surface.n96),
            "&:hover": {
              backgroundColor: COLORS.surface.n96
            }
          }
        }
      ]
    }
  }
})


const materialLocales = { es: materialEs, zh: materialZh };
const pickerLocales = { es: pickerEs, zh: pickerZh };
const dateLocales = { es: 'es', zh: 'zh-cn', en: 'en' };

const LocalizedApplication = () => {
  const { i18n } = useTranslation();
  const language = (i18n.resolvedLanguage || i18n.language || 'es').split('-')[0];
  const localizedTheme = React.useMemo(
    () => createTheme(v5Theme, materialLocales[language] || {}, pickerLocales[language] || {}),
    [language],
  );
  return (
    <HashRouter>
      <StyledEngineProvider injectFirst>
        <ThemeProvider theme={localizedTheme}>
          <LocalizationProvider dateAdapter={AdapterMoment} adapterLocale={dateLocales[language] || 'en'}>
            <LayoutContext subPages={(<App />)} />
          </LocalizationProvider>
        </ThemeProvider>
      </StyledEngineProvider>
    </HashRouter>
  );
};

const container = document.getElementById('root');
const root = createRoot(container);
root.render(<LocalizedApplication />);
