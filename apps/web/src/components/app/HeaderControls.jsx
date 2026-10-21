import React from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton'
import AddIcon from '@mui/icons-material/Add'
import ImportIcon from '@mui/icons-material/Publish';
import UserMenu from '../users/UserMenu';
import UserProfileButton from '../users/UserProfileButton';
import AddMenuList from '../users/AddMenuList'
import { isLoggedIn, isSelfRegistrationEnabled } from '../../common/utils';

const HeaderControls = () => {
  const { t } = useTranslation()
  const [userMenu, setUserMenu] = React.useState(false)
  const [addMenu, setAddMenu] = React.useState(false)
  const [addMenuAnchorEl, setAddMenuAnchorEl] = React.useState(false)

  const onAddMenuOpen = event => {
    setAddMenuAnchorEl(event.currentTarget)
    setAddMenu(true)
  }
  const onAddMenuClose = () => {
    setAddMenuAnchorEl(false)
    setAddMenu(false)
  }

  const authenticated = isLoggedIn()
  const signInHref = `#/signin?returnTo=${encodeURIComponent(window.location.href)}`

  return (
    <Box sx={{ gridArea: 'controls', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
      {
        authenticated ?
          <>
            <IconButton aria-label={t('common.import')} sx={{minWidth: 44, minHeight: 44}} href="#/imports">
              <ImportIcon />
            </IconButton>
            <IconButton aria-label={t('common.create')} aria-expanded={addMenu} sx={{minWidth: 44, minHeight: 44}} onClick={onAddMenuOpen}>
              <AddIcon />
            </IconButton>
          </> :
          <>
            <Button href={signInHref} sx={{display: {xs: isSelfRegistrationEnabled() ? 'none' : 'inline-flex', md: 'inline-flex'}, textTransform: 'none', whiteSpace: 'nowrap', minHeight: 44}}>
              {t('auth.sign_in')}
            </Button>
            {isSelfRegistrationEnabled() && (
              <Button href='#/signup' variant='contained' disableElevation sx={{borderRadius: '100px', textTransform: 'none', whiteSpace: 'nowrap', minHeight: 44, px: 2}}>
                {t('auth.register')}
              </Button>
            )}
          </>
      }
      <UserProfileButton aria-label={t('common.account_menu')} aria-expanded={userMenu} sx={{minWidth: 44, minHeight: 44}} onClick={() => setUserMenu(true)} />
      <UserMenu isOpen={userMenu} onClose={() => setUserMenu(false)} />
      {authenticated && <AddMenuList open={addMenu} onClose={onAddMenuClose} anchorEl={addMenuAnchorEl} />}
    </Box>
  )
}

export default HeaderControls;
