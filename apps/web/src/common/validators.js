import {has, forEach, isEmpty, isNumber} from "lodash";
import i18n from 'i18next';

export const MESSAGES = {
  get REQUIRED() { return i18n.t('errors.mandatory_field'); },
  get SELECTED() { return i18n.t('errors.select_from_suggestions'); },
  get PATTERN() { return i18n.t('errors.invalid_value'); }
};

export const VALUE_NOT_SELECTED = 'VALUE_NOT_SELECTED';

export const  required = (msg='') => getValidator(
  value => isEmpty(value) && !isNumber(value),
  msg, 'REQUIRED',
);

export const selected = (msg='') => getValidator(
  value => ('' + value).length && value === VALUE_NOT_SELECTED,
  msg, 'SELECTED',
);

export const matchPattern = (pattern, msg='') => getValidator(
  value => value?.length && !value.match(pattern)?.length,
  msg, 'PATTERN',
);


export const applyValidatorsOn = fields => {
  forEach(fields, (field) => {
    if(has(field, 'value') && has(field, 'validators')){
      field.errors = [];
      field.validators.forEach((validator) => {
        if(validator.isInvalid(field.value)) {
          field.errors.push(validator.message);
        }
      });
    }
  });
};

const getValidator = (isInvalidFunction, message, defaultMessage, type='error') => {
  return {
    isInvalid: isInvalidFunction,
    // Forms can keep a validator while the user changes the interface language.
    get message() { return message || MESSAGES[defaultMessage]; },
    type,
  };
}
