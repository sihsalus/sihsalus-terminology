import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert, Button } from '@mui/material'
import { getRegisterURL, isSelfRegistrationEnabled, isSSOConfigured } from '../../common/utils'
import LocalSignup from '../users/LocalSignup'

const SignupRedirect = () => {
  const { t } = useTranslation()
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if(!isSelfRegistrationEnabled() || !isSSOConfigured()) return
    let active = true
    setFailed(false)
    getRegisterURL()
      .then(url => { if(active) window.location.href = url })
      .catch(() => { if(active) setFailed(true) })
    return () => { active = false }
  }, [attempt]);

  if(!isSelfRegistrationEnabled()) return <h4>{t('auth.managed_accounts')}</h4>
  if(!isSSOConfigured()) return <LocalSignup />
  return failed ?
    <Alert severity='error' action={<Button onClick={() => setAttempt(value => value + 1)}>{t('common.try_again')}</Button>}>{t('auth.redirect_failed')}</Alert> :
    <h4 role='status'>{t('auth.redirecting')}</h4>
};

export default SignupRedirect;
