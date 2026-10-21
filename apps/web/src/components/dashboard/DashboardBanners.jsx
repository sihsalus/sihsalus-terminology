import React from 'react';
import { useTranslation } from 'react-i18next'
import { Box, Button, Typography } from '@mui/material'
import { WHITE, PRIMARY_COLORS } from '../../common/colors'
import { isSelfRegistrationEnabled } from '../../common/utils'
import ConceptIcon from '../concepts/ConceptIcon'

const DashboardBanners = () => {
  const { t } = useTranslation()
  const canRegister = isSelfRegistrationEnabled()

  return (
    <Box sx={{borderRadius: '10px', background: PRIMARY_COLORS.main, color: WHITE, p: 3, overflowWrap: 'anywhere'}}>
      <ConceptIcon selected sx={{color: WHITE, width: '40px', height: '40px', mb: 1}} />
      <Typography component='h2' sx={{fontSize: '24px', fontWeight: 'bold', mb: 2}}>
        {t('dashboard.welcome_title')}
      </Typography>
      <Typography sx={{fontSize: '16px', mb: 2}}>{t('dashboard.welcome_description')}</Typography>
      <Typography sx={{fontSize: '14px', mb: 3}}>
        {t(canRegister ? 'dashboard.welcome_registration' : 'auth.managed_accounts')}
      </Typography>
      <Button
        href={canRegister ? '#/signup' : '#/signin'}
        fullWidth
        variant='contained'
        sx={{borderRadius: '100px', textTransform: 'none', backgroundColor: 'primary.dark', color: 'primary.20'}}
      >
        {t(canRegister ? 'auth.register' : 'auth.sign_in')}
      </Button>
    </Box>
  )
}

export default DashboardBanners
