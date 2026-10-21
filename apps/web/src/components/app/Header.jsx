import React from 'react';
import { useTranslation } from 'react-i18next'
import { styled } from '@mui/material/styles';
import Box from '@mui/material/Box';
import MuiAppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import CssBaseline from '@mui/material/CssBaseline';
import MenuIcon from '@mui/icons-material/Menu';
import { COLORS } from '../../common/colors';
import { getCurrentUser, getSiteTitle } from '../../common/utils';
import SearchInput from '../search/SearchInput';
import './Header.scss';
import HeaderControls from './HeaderControls';
import LeftMenu from './LeftMenu'

const AppBar = styled(MuiAppBar)(({ theme }) => ({
  zIndex: theme.zIndex.drawer + 1,
}));

const Header = props => {
  const { t } = useTranslation()
  const user = getCurrentUser()
  const [open, setOpen] = React.useState(false);
  const [headerHeight, setHeaderHeight] = React.useState(null);
  const headerRef = React.useRef(null);
  const handleDrawerOpen = () => setOpen(!open);

  React.useLayoutEffect(() => {
    const element = headerRef.current;
    const measure = () => setHeaderHeight(element.getBoundingClientRect().height);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <Box sx={{ display: 'flex', '--app-header-height': headerHeight ? `${headerHeight}px` : { xs: '112px', md: '64px' } }}>
      <CssBaseline />
      <AppBar ref={headerRef} position="fixed" sx={{
        top: 'var(--announcement-height, 0px)',
        backgroundColor: COLORS.surface.n96,
        color: COLORS.surface.contrastText,
        boxShadow: 'none',
      }}>
        <Toolbar className='site-header-toolbar' sx={{
          display: 'grid',
          gridTemplateColumns: { xs: 'minmax(0, 1fr) auto', md: 'minmax(180px, 1fr) minmax(220px, 1.4fr) auto' },
          gridTemplateAreas: { xs: '"brand controls" "search search"', md: '"brand search controls"' },
          columnGap: { xs: 1, md: 2 },
          rowGap: 1,
          py: { xs: 1, md: 0 },
          px: { xs: 1.5, sm: 2 },
          minHeight: { xs: 112, md: 64 },
        }}>
          <Box sx={{ gridArea: 'brand', display: 'flex', alignItems: 'center', minWidth: 0, minHeight: 48 }}>
            {
              Boolean(user?.url) &&
                <IconButton
                  color="inherit"
                  aria-label={t('common.open_navigation')}
                  aria-expanded={open}
                  onClick={handleDrawerOpen}
                  edge="start"
                  sx={{ mr: 0.5, flexShrink: 0, minWidth: 44, minHeight: 44 }}
                >
                  <MenuIcon />
                </IconButton>
            }
            <Typography component='a' href='/#/' variant='subtitle1' sx={{
              fontWeight: 700, color: 'primary.main', textDecoration: 'none',
              fontSize: { xs: '0.875rem', sm: '1rem' }, lineHeight: 1.3, overflowWrap: 'anywhere',
            }}>
              {getSiteTitle()}
            </Typography>
          </Box>
          <Box sx={{ gridArea: 'search', minWidth: 0 }}>
            <SearchInput size='small' style={{width: '100%'}} placeholder={t('search.input_placeholder')} />
          </Box>
          <HeaderControls />
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column', height: '100dvh', paddingTop: 0, px: { xs: 1.5, sm: 2 } }}>
        <Box aria-hidden sx={{ height: 'var(--app-header-height)', flexShrink: 0, marginTop: 'var(--announcement-height, 0px)' }} />
        {props.children}
      </Box>
      <LeftMenu isOpen={open} onClose={handleDrawerOpen} />
    </Box>
  );
}

export default Header;
