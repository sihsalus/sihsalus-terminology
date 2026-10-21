import React from 'react';
import { Trans } from 'react-i18next';
import { Box, LinearProgress } from '@mui/material'
import { BLACK } from '../../common/colors'

const AutocompleteLoading = ({ text }) => {

  return (
    <React.Fragment>
      <Box sx={{ width: '100%', margin: '20px 0', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
        {
          text &&
            <div className='col-xs-12' style={{width: '100%', textAlign: 'center', marginBottom: '10px', color: BLACK}}>
              <Trans i18nKey="common.loading_results_for" values={{query: text}} components={{strong: <b />}} shouldUnescape />
            </div>
        }
        <div className='col-xs-8'>
          <LinearProgress />
        </div>
      </Box>

    </React.Fragment>
  )
}

export default AutocompleteLoading;
