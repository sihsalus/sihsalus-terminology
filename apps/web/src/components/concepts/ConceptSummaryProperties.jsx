import React from 'react'
import { useTranslation } from 'react-i18next'
import Property from './Property'

import keys from 'lodash/keys'
import get from 'lodash/get'
import map from 'lodash/map'
import without from 'lodash/without'


const ConceptSummaryProperties = ({concept}) => {
  const { t } = useTranslation()
  const getProperties = () => {
    if(concept.property?.length > 0) {
      let values = []
      concept.property.forEach(prop => {
        if(prop?.code){
        let label = prop?.display || prop?.code
        let value;
        if(['concept_class', 'datatype'].includes(label))
          label = t(`concept.${label}`)
          value = get(prop, get(without(keys(prop), 'code'), '0'))
          values.push(<Property key={label} code={label} value={value} />)
        }
      })
      return values
    }
    return [
      <Property key={1} code={t('concept.concept_class')} value={concept.concept_class} />,
      <Property key={2} code={t('concept.datatype')} value={concept.datatype} />,
    ]
  }

  return (
    <>
      {map(getProperties(), prop => prop)}
    </>
  )
}

export default ConceptSummaryProperties
