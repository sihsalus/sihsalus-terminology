import React, { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getRegisterURL, isSelfRegistrationEnabled, isSSOConfigured } from '../../common/utils'

import LocalSignup from '../users/LocalSignup'

const SignupRedirect = () => {
  const { t } = useTranslation()
  useEffect(() => {
    if(!isSelfRegistrationEnabled() || !isSSOConfigured()) return
    getRegisterURL().then(url => { window.location.href = url });
  }, []);

  if(!isSelfRegistrationEnabled()) return <h4>{t('auth.managed_accounts')}</h4>
  return isSSOConfigured() ? <h4>Redirecting...</h4> : <LocalSignup />
};

export default SignupRedirect;
