/**
 * Utilitarios puros de validacao e formatacao usados pelas telas de
 * autenticacao (login, cadastro e recuperacao de senha).
 *
 * Todas as funcoes de validacao retornam `null` quando o valor e valido,
 * ou uma mensagem de erro padronizada em pt-BR para uso nos estados de
 * feedback visual dos formularios.
 */

/** Formata progressivamente uma string de digitos como CPF (000.000.000-00). */
export function formatCpf(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`;
  if (digits.length <= 9)
    return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`;
  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9)}`;
}

/** Formata progressivamente uma string de digitos como data (DD/MM/AAAA). */
export function formatDateInput(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

interface ParsedDdMmAaaa {
  day: string;
  month: string;
  year: string;
  date: Date;
}

/**
 * Interpreta uma string no formato dd/mm/aaaa em suas partes e no `Date`
 * correspondente, validando que a data realmente existe no calendario.
 * Retorna `null` quando o formato ou a data sao invalidos.
 */
function parseDdMmAaaa(dateStr: string): ParsedDdMmAaaa | null {
  const parts = dateStr.split('/');
  if (parts.length !== 3) return null;
  const [day, month, year] = parts;
  if (!/^\d{2}$/.test(day) || !/^\d{2}$/.test(month) || !/^\d{4}$/.test(year)) {
    return null;
  }

  const dayNum = Number(day);
  const monthNum = Number(month);
  const yearNum = Number(year);

  const date = new Date(yearNum, monthNum - 1, dayNum);
  const isRealDate =
    date.getFullYear() === yearNum &&
    date.getMonth() === monthNum - 1 &&
    date.getDate() === dayNum;
  if (!isRealDate) return null;

  return { day, month, year, date };
}

/**
 * Converte uma data no formato dd/mm/aaaa para ISO (aaaa-mm-dd).
 * Retorna `undefined` quando a entrada esta vazia, incompleta ou representa
 * uma data invalida/inexistente ou no futuro.
 */
export function parseDateToISO(dateStr: string): string | undefined {
  if (!dateStr.trim()) return undefined;
  const parsed = parseDdMmAaaa(dateStr);
  if (!parsed) return undefined;
  if (parsed.date.getTime() > Date.now()) return undefined;
  return `${parsed.year}-${parsed.month}-${parsed.day}`;
}

/** Remove todos os caracteres nao numericos de uma string. */
function onlyDigits(value: string): string {
  return value.replace(/\D/g, '');
}

/** Calcula um digito verificador de CPF a partir dos digitos base e do peso inicial. */
function calcCpfDigit(digits: string, weightStart: number): number {
  let sum = 0;
  for (let i = 0; i < digits.length; i += 1) {
    sum += Number(digits[i]) * (weightStart - i);
  }
  const remainder = (sum * 10) % 11;
  return remainder === 10 ? 0 : remainder;
}

/**
 * Valida um CPF (formatado ou apenas digitos), incluindo digitos
 * verificadores. Retorna `null` quando valido.
 */
export function validateCpf(value: string): string | null {
  const digits = onlyDigits(value);

  if (!digits.trim()) {
    return 'CPF e obrigatorio.';
  }

  if (digits.length !== 11) {
    return 'CPF deve conter 11 digitos.';
  }

  if (/^(\d)\1{10}$/.test(digits)) {
    return 'CPF invalido.';
  }

  const firstDigit = calcCpfDigit(digits.slice(0, 9), 10);
  const secondDigit = calcCpfDigit(digits.slice(0, 10), 11);

  if (firstDigit !== Number(digits[9]) || secondDigit !== Number(digits[10])) {
    return 'CPF invalido.';
  }

  return null;
}

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Valida um endereco de e-mail. Retorna `null` quando valido. */
export function validateEmail(value: string): string | null {
  if (!value.trim()) {
    return 'E-mail e obrigatorio.';
  }
  if (!EMAIL_REGEX.test(value.trim())) {
    return 'E-mail invalido.';
  }
  return null;
}

/**
 * Valida uma senha: obrigatoria, minimo de 8 caracteres e presenca de
 * letras e numeros. Retorna `null` quando valida.
 */
export function validatePassword(value: string): string | null {
  if (!value.trim()) {
    return 'Senha e obrigatoria.';
  }
  if (value.length < 8) {
    return 'Senha deve ter no minimo 8 caracteres.';
  }
  if (!/[a-zA-Z]/.test(value) || !/\d/.test(value)) {
    return 'Senha deve conter letras e numeros.';
  }
  return null;
}

/**
 * Valida uma data de nascimento no formato dd/mm/aaaa. Campo opcional:
 * retorna `null` quando vazio. Retorna `null` quando valida.
 */
export function validateBirthDate(value: string): string | null {
  if (!value.trim()) {
    return null;
  }

  const parsed = parseDdMmAaaa(value);
  if (!parsed) {
    return 'Data de nascimento invalida.';
  }

  if (parsed.date.getTime() > Date.now()) {
    return 'Data de nascimento nao pode ser no futuro.';
  }

  return null;
}

/** Valores do formulario de cadastro, incluindo o campo opcional de data de nascimento. */
export interface RegisterFormValues {
  full_name: string;
  cpf: string;
  birth_date: string;
  email: string;
  username: string;
  password: string;
}

/** Mapa de erros por campo do formulario de cadastro (chave -> mensagem). */
export type RegisterFormErrors = Partial<Record<keyof RegisterFormValues, string>>;

/**
 * Valida um unico campo do formulario de cadastro e retorna sua mensagem de
 * erro, ou `null` quando o campo e valido.
 */
export function validateRegisterField(
  field: keyof RegisterFormValues,
  values: RegisterFormValues
): string | null {
  switch (field) {
    case 'full_name':
      return values.full_name.trim() ? null : 'Nome completo e obrigatorio.';
    case 'cpf':
      return validateCpf(values.cpf);
    case 'birth_date':
      return validateBirthDate(values.birth_date);
    case 'email':
      return validateEmail(values.email);
    case 'username':
      return values.username.trim() ? null : 'Usuario e obrigatorio.';
    case 'password':
      return validatePassword(values.password);
    default:
      return null;
  }
}

/**
 * Valida todos os campos do formulario de cadastro e retorna um mapa de
 * erros por campo (campo -> mensagem). Campos validos nao aparecem no
 * objeto retornado; quando tudo e valido, retorna um objeto vazio.
 */
export function validateRegisterForm(values: RegisterFormValues): RegisterFormErrors {
  const fields: (keyof RegisterFormValues)[] = [
    'full_name',
    'cpf',
    'birth_date',
    'email',
    'username',
    'password',
  ];

  const errors: RegisterFormErrors = {};
  fields.forEach((field) => {
    const error = validateRegisterField(field, values);
    if (error) {
      errors[field] = error;
    }
  });
  return errors;
}

/**
 * Verifica se usuario e senha do formulario de login foram preenchidos
 * (ignorando espacos). Retorna `null` quando ambos estao preenchidos.
 */
export function validateLoginFields(username: string, password: string): string | null {
  if (!username.trim() || !password.trim()) {
    return 'Preencha todos os campos obrigatorios.';
  }
  return null;
}
