import React, { useEffect } from 'react'
import { getLoginURL, isSSOConfigured } from '../../common/utils'
import LocalSignIn from '../users/LocalSignIn'

const SigninRedirect = props => {
  useEffect(() => {
    if(!isSSOConfigured()) return
    const queryParams = new URLSearchParams(props.location?.search)
    const returnTo = queryParams.get('returnTo')
    getLoginURL(returnTo).then(url => { window.location.href = url });
  }, []);

  return isSSOConfigured() ? <h4>Redirecting...</h4> : <LocalSignIn />;
};

export default SigninRedirect;
