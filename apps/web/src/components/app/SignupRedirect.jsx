import React, { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getRegisterURL, isSelfRegistrationEnabled } from '../../common/utils'

const SignupRedirect = () => {
  const { t } = useTranslation()
  useEffect(() => {
    if(!isSelfRegistrationEnabled()) return
    getRegisterURL().then(url => { window.location.href = url });
  }, []);

  return <h4>{isSelfRegistrationEnabled() ? 'Redirecting...' : t('auth.managed_accounts')}</h4>;
};

export default SignupRedirect;
