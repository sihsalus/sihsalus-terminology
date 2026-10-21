import React from 'react';
import { useTranslation } from 'react-i18next';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';

const RepoTabs = ({TABS, sx, ...rest}) => {
  const { t } = useTranslation()
  return (
    <Tabs
      indicatorColor="primary"
      variant="fullWidth"
      aria-label={t('common.tabs')}
      sx={{backgroundColor: 'surface.main', width: '100%', borderTop: '0.3px solid', borderBottom: '0.3px solid', borderColor: 'surface.nv80', ...sx}}
      {...rest}
    >
      {
        TABS.map(resource => (
          <Tab
            key={resource.key}
            className='tab-anchor'
            value={resource.key}
            label={resource.label}
          sx={{color: 'surface.contrastText', fontWeight: 'bold'}}
          />
        ))
      }
    </Tabs>
  )
}

export default RepoTabs
