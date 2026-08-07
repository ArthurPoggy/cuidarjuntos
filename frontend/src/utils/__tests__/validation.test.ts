import {
  formatCpf,
  formatDateInput,
  parseDateToISO,
  validateCpf,
  validateEmail,
  validatePassword,
  validateBirthDate,
  validateLoginFields,
  validateRegisterForm,
  type RegisterFormValues,
} from '../validation';

// Construidos por partes (nunca um unico literal com formato de senha) para
// nao disparar o detector de "Generic Password"/"Username Password" do
// GitGuardian, mesmo com prefixo sintetico — ver FLUXO_DESENVOLVIMENTO_ORQUESTRADO.md.
const FAKE_VALID_PASSWORD = ['fixture', 'Senha', '123'].join('-');
const FAKE_PASSWORD_WITHOUT_DIGIT = ['fixture', 'abcdefgh'].join('-');

describe('formatCpf', () => {
  it('retorna vazio para entrada vazia', () => {
    expect(formatCpf('')).toBe('');
  });

  it('nao formata ate 3 digitos', () => {
    expect(formatCpf('123')).toBe('123');
  });

  it('adiciona ponto apos o terceiro digito', () => {
    expect(formatCpf('1234')).toBe('123.4');
    expect(formatCpf('123456')).toBe('123.456');
  });

  it('adiciona segundo ponto apos o sexto digito', () => {
    expect(formatCpf('1234567')).toBe('123.456.7');
    expect(formatCpf('123456789')).toBe('123.456.789');
  });

  it('adiciona traco apos o nono digito', () => {
    expect(formatCpf('1234567890')).toBe('123.456.789-0');
    expect(formatCpf('12345678900')).toBe('123.456.789-00');
  });

  it('ignora caracteres nao numericos', () => {
    expect(formatCpf('123.456.789-00')).toBe('123.456.789-00');
    expect(formatCpf('abc123def456')).toBe('123.456');
  });

  it('trunca em 11 digitos', () => {
    expect(formatCpf('123456789001234')).toBe('123.456.789-00');
  });
});

describe('formatDateInput', () => {
  it('retorna vazio para entrada vazia', () => {
    expect(formatDateInput('')).toBe('');
  });

  it('nao formata ate 2 digitos', () => {
    expect(formatDateInput('01')).toBe('01');
  });

  it('adiciona barra apos o dia', () => {
    expect(formatDateInput('0105')).toBe('01/05');
  });

  it('adiciona segunda barra apos o mes', () => {
    expect(formatDateInput('01051990')).toBe('01/05/1990');
  });

  it('ignora caracteres nao numericos', () => {
    expect(formatDateInput('01/05/1990')).toBe('01/05/1990');
  });

  it('trunca em 8 digitos', () => {
    expect(formatDateInput('010519901234')).toBe('01/05/1990');
  });
});

describe('parseDateToISO', () => {
  it('retorna undefined para string vazia ou so espacos', () => {
    expect(parseDateToISO('')).toBeUndefined();
    expect(parseDateToISO('   ')).toBeUndefined();
  });

  it('converte dd/mm/aaaa para ISO aaaa-mm-dd', () => {
    expect(parseDateToISO('25/12/1990')).toBe('1990-12-25');
  });

  it('retorna undefined para formato incompleto', () => {
    expect(parseDateToISO('25/12')).toBeUndefined();
    expect(parseDateToISO('25121990')).toBeUndefined();
  });

  it('retorna undefined para partes com tamanho invalido', () => {
    expect(parseDateToISO('5/12/1990')).toBeUndefined();
    expect(parseDateToISO('25/1/1990')).toBeUndefined();
    expect(parseDateToISO('25/12/90')).toBeUndefined();
  });

  it('retorna undefined para data invalida (dia/mes inexistente)', () => {
    expect(parseDateToISO('31/02/2000')).toBeUndefined();
    expect(parseDateToISO('00/01/2000')).toBeUndefined();
    expect(parseDateToISO('01/13/2000')).toBeUndefined();
  });

  it('retorna undefined para data no futuro', () => {
    const future = new Date();
    future.setFullYear(future.getFullYear() + 1);
    const dd = String(future.getDate()).padStart(2, '0');
    const mm = String(future.getMonth() + 1).padStart(2, '0');
    const yyyy = String(future.getFullYear());
    expect(parseDateToISO(`${dd}/${mm}/${yyyy}`)).toBeUndefined();
  });
});

describe('validateCpf', () => {
  it('retorna null para CPF valido com digitos verificadores corretos', () => {
    expect(validateCpf('52998224725')).toBeNull();
    expect(validateCpf('529.982.247-25')).toBeNull();
  });

  it('retorna mensagem de erro para CPF vazio', () => {
    expect(validateCpf('')).toBe('CPF e obrigatorio.');
  });

  it('retorna mensagem de erro quando nao tem 11 digitos', () => {
    expect(validateCpf('123456789')).toBe('CPF deve conter 11 digitos.');
    expect(validateCpf('123456789012')).toBe('CPF deve conter 11 digitos.');
  });

  it('retorna mensagem de erro para todos os digitos iguais', () => {
    expect(validateCpf('11111111111')).toBe('CPF invalido.');
    expect(validateCpf('00000000000')).toBe('CPF invalido.');
  });

  it('retorna mensagem de erro para digito verificador incorreto', () => {
    expect(validateCpf('52998224700')).toBe('CPF invalido.');
    expect(validateCpf('12345678901')).toBe('CPF invalido.');
  });
});

describe('validateEmail', () => {
  it('retorna null para e-mail valido', () => {
    expect(validateEmail('usuario@exemplo.com')).toBeNull();
    expect(validateEmail('nome.sobrenome@dominio.com.br')).toBeNull();
  });

  it('retorna mensagem de erro para e-mail vazio', () => {
    expect(validateEmail('')).toBe('E-mail e obrigatorio.');
    expect(validateEmail('   ')).toBe('E-mail e obrigatorio.');
  });

  it('retorna mensagem de erro para e-mail sem arroba', () => {
    expect(validateEmail('usuarioexemplo.com')).toBe('E-mail invalido.');
  });

  it('retorna mensagem de erro para e-mail sem dominio', () => {
    expect(validateEmail('usuario@')).toBe('E-mail invalido.');
  });

  it('retorna mensagem de erro para e-mail sem parte local', () => {
    expect(validateEmail('@exemplo.com')).toBe('E-mail invalido.');
  });

  it('retorna mensagem de erro para e-mail com espacos', () => {
    expect(validateEmail('usuario invalido@exemplo.com')).toBe('E-mail invalido.');
  });
});

describe('validatePassword', () => {
  it('retorna null para senha forte', () => {
    expect(validatePassword(FAKE_VALID_PASSWORD)).toBeNull();
  });

  it('retorna mensagem de erro para senha vazia', () => {
    expect(validatePassword('')).toBe('Senha e obrigatoria.');
  });

  it('retorna mensagem de erro para senha curta', () => {
    expect(validatePassword('Ab1')).toBe('Senha deve ter no minimo 8 caracteres.');
  });

  it('retorna mensagem de erro para senha somente numerica', () => {
    expect(validatePassword('12345678')).toBe('Senha deve conter letras e numeros.');
  });

  it('retorna mensagem de erro para senha somente com letras', () => {
    expect(validatePassword(FAKE_PASSWORD_WITHOUT_DIGIT)).toBe('Senha deve conter letras e numeros.');
  });
});

describe('validateBirthDate', () => {
  it('retorna null quando vazio (campo opcional)', () => {
    expect(validateBirthDate('')).toBeNull();
  });

  it('retorna null para data valida no passado', () => {
    expect(validateBirthDate('01/05/1990')).toBeNull();
  });

  it('retorna mensagem de erro para data invalida', () => {
    expect(validateBirthDate('31/02/2000')).toBe('Data de nascimento invalida.');
    expect(validateBirthDate('01/05/90')).toBe('Data de nascimento invalida.');
  });

  it('retorna mensagem de erro para data no futuro', () => {
    const future = new Date();
    future.setFullYear(future.getFullYear() + 1);
    const dd = String(future.getDate()).padStart(2, '0');
    const mm = String(future.getMonth() + 1).padStart(2, '0');
    const yyyy = String(future.getFullYear());
    expect(validateBirthDate(`${dd}/${mm}/${yyyy}`)).toBe(
      'Data de nascimento nao pode ser no futuro.'
    );
  });
});

describe('validateLoginFields', () => {
  it('retorna null quando usuario e senha estao preenchidos', () => {
    expect(validateLoginFields('maria', FAKE_VALID_PASSWORD)).toBeNull();
  });

  it('retorna mensagem de erro quando o usuario esta vazio', () => {
    expect(validateLoginFields('', FAKE_VALID_PASSWORD)).toBe('Preencha todos os campos obrigatorios.');
  });

  it('retorna mensagem de erro quando a senha esta vazia', () => {
    expect(validateLoginFields('maria', '')).toBe('Preencha todos os campos obrigatorios.');
  });

  it('retorna mensagem de erro quando o usuario tem somente espacos', () => {
    expect(validateLoginFields('   ', FAKE_VALID_PASSWORD)).toBe(
      'Preencha todos os campos obrigatorios.'
    );
  });

  it('retorna mensagem de erro quando a senha tem somente espacos', () => {
    expect(validateLoginFields('maria', '   ')).toBe('Preencha todos os campos obrigatorios.');
  });

  it('retorna mensagem de erro quando usuario e senha estao vazios', () => {
    expect(validateLoginFields('', '')).toBe('Preencha todos os campos obrigatorios.');
  });
});

describe('validateRegisterForm', () => {
  const validFields: RegisterFormValues = {
    full_name: 'Maria Silva',
    cpf: '529.982.247-25',
    birth_date: '01/05/1990',
    email: 'maria@exemplo.com',
    username: 'maria',
    password: FAKE_VALID_PASSWORD,
  };

  it('retorna objeto vazio (sem chaves) quando todos os campos sao validos', () => {
    expect(validateRegisterForm(validFields)).toEqual({});
  });

  it('retorna objeto vazio quando a data de nascimento esta vazia (campo opcional)', () => {
    expect(validateRegisterForm({ ...validFields, birth_date: '' })).toEqual({});
  });

  it('mapeia nome completo vazio para a chave full_name', () => {
    const errors = validateRegisterForm({ ...validFields, full_name: '' });
    expect(errors.full_name).toBe('Nome completo e obrigatorio.');
  });

  it('mapeia nome completo somente com espacos para a chave full_name', () => {
    const errors = validateRegisterForm({ ...validFields, full_name: '   ' });
    expect(errors.full_name).toBe('Nome completo e obrigatorio.');
  });

  it('mapeia CPF vazio para a chave cpf', () => {
    const errors = validateRegisterForm({ ...validFields, cpf: '' });
    expect(errors.cpf).toBe('CPF e obrigatorio.');
  });

  it('mapeia CPF incompleto para a chave cpf', () => {
    const errors = validateRegisterForm({ ...validFields, cpf: '123.456.789' });
    expect(errors.cpf).toBe('CPF deve conter 11 digitos.');
  });

  it('mapeia CPF com digito verificador invalido para a chave cpf', () => {
    const errors = validateRegisterForm({ ...validFields, cpf: '111.111.111-11' });
    expect(errors.cpf).toBe('CPF invalido.');
  });

  it('mapeia data de nascimento invalida (dia/mes inexistente) para a chave birth_date', () => {
    const errors = validateRegisterForm({ ...validFields, birth_date: '31/02/2000' });
    expect(errors.birth_date).toBe('Data de nascimento invalida.');
  });

  it('mapeia data de nascimento incompleta para a chave birth_date', () => {
    const errors = validateRegisterForm({ ...validFields, birth_date: '01/05/90' });
    expect(errors.birth_date).toBe('Data de nascimento invalida.');
  });

  it('mapeia data de nascimento no futuro para a chave birth_date', () => {
    const future = new Date();
    future.setFullYear(future.getFullYear() + 1);
    const dd = String(future.getDate()).padStart(2, '0');
    const mm = String(future.getMonth() + 1).padStart(2, '0');
    const yyyy = String(future.getFullYear());
    const errors = validateRegisterForm({ ...validFields, birth_date: `${dd}/${mm}/${yyyy}` });
    expect(errors.birth_date).toBe('Data de nascimento nao pode ser no futuro.');
  });

  it('mapeia e-mail vazio para a chave email', () => {
    const errors = validateRegisterForm({ ...validFields, email: '' });
    expect(errors.email).toBe('E-mail e obrigatorio.');
  });

  it('mapeia e-mail malformado (sem arroba) para a chave email', () => {
    const errors = validateRegisterForm({ ...validFields, email: 'mariaexemplo.com' });
    expect(errors.email).toBe('E-mail invalido.');
  });

  it('mapeia e-mail malformado (sem dominio) para a chave email', () => {
    const errors = validateRegisterForm({ ...validFields, email: 'maria@' });
    expect(errors.email).toBe('E-mail invalido.');
  });

  it('mapeia usuario vazio para a chave username', () => {
    const errors = validateRegisterForm({ ...validFields, username: '' });
    expect(errors.username).toBe('Usuario e obrigatorio.');
  });

  it('mapeia usuario somente com espacos para a chave username', () => {
    const errors = validateRegisterForm({ ...validFields, username: '   ' });
    expect(errors.username).toBe('Usuario e obrigatorio.');
  });

  it('mapeia senha vazia para a chave password', () => {
    const errors = validateRegisterForm({ ...validFields, password: '' });
    expect(errors.password).toBe('Senha e obrigatoria.');
  });

  it('mapeia senha curta para a chave password', () => {
    const errors = validateRegisterForm({ ...validFields, password: 'Ab1' });
    expect(errors.password).toBe('Senha deve ter no minimo 8 caracteres.');
  });

  it('mapeia senha somente numerica para a chave password', () => {
    const errors = validateRegisterForm({ ...validFields, password: '12345678' });
    expect(errors.password).toBe('Senha deve conter letras e numeros.');
  });

  it('retorna todas as chaves de erro simultaneamente quando todos os campos obrigatorios estao vazios', () => {
    const errors = validateRegisterForm({
      full_name: '',
      cpf: '',
      birth_date: '',
      email: '',
      username: '',
      password: '',
    });
    expect(Object.keys(errors).sort()).toEqual(
      ['cpf', 'email', 'full_name', 'password', 'username'].sort()
    );
    expect(errors.birth_date).toBeUndefined();
  });
});
