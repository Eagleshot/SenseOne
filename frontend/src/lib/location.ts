const FLAG_EMOJI_REGEX = /(?:\uD83C[\uDDE6-\uDDFF]){2}/;
const DIACRITIC_REGEX = /[\u0300-\u036f]/g;

const COUNTRY_ALIASES: Record<string, string> = {
  afghanistan: 'AF',
  albania: 'AL',
  algeria: 'DZ',
  andorra: 'AD',
  angola: 'AO',
  'antigua and barbuda': 'AG',
  argentina: 'AR',
  armenia: 'AM',
  australia: 'AU',
  austria: 'AT',
  azerbaijan: 'AZ',
  bahamas: 'BS',
  bahrain: 'BH',
  bangladesh: 'BD',
  barbados: 'BB',
  belarus: 'BY',
  belgium: 'BE',
  belize: 'BZ',
  benin: 'BJ',
  bhutan: 'BT',
  bolivia: 'BO',
  'bosnia and herzegovina': 'BA',
  botswana: 'BW',
  brazil: 'BR',
  brunei: 'BN',
  bulgaria: 'BG',
  'burkina faso': 'BF',
  burundi: 'BI',
  'cabo verde': 'CV',
  cambodia: 'KH',
  cameroon: 'CM',
  canada: 'CA',
  'central african republic': 'CF',
  chad: 'TD',
  chile: 'CL',
  china: 'CN',
  colombia: 'CO',
  comoros: 'KM',
  'congo republic of the': 'CG',
  'republic of the congo': 'CG',
  'costa rica': 'CR',
  croatia: 'HR',
  cuba: 'CU',
  cyprus: 'CY',
  'czech republic': 'CZ',
  denmark: 'DK',
  djibouti: 'DJ',
  dominica: 'DM',
  'dominican republic': 'DO',
  ecuador: 'EC',
  egypt: 'EG',
  'el salvador': 'SV',
  'equatorial guinea': 'GQ',
  eritrea: 'ER',
  estonia: 'EE',
  eswatini: 'SZ',
  ethiopia: 'ET',
  fiji: 'FJ',
  finland: 'FI',
  france: 'FR',
  gabon: 'GA',
  gambia: 'GM',
  georgia: 'GE',
  germany: 'DE',
  ghana: 'GH',
  greece: 'GR',
  grenada: 'GD',
  guatemala: 'GT',
  guinea: 'GN',
  'guinea bissau': 'GW',
  guyana: 'GY',
  haiti: 'HT',
  honduras: 'HN',
  hungary: 'HU',
  iceland: 'IS',
  india: 'IN',
  indonesia: 'ID',
  iran: 'IR',
  iraq: 'IQ',
  ireland: 'IE',
  israel: 'IL',
  italy: 'IT',
  jamaica: 'JM',
  japan: 'JP',
  jordan: 'JO',
  kazakhstan: 'KZ',
  kenya: 'KE',
  kiribati: 'KI',
  kuwait: 'KW',
  kyrgyzstan: 'KG',
  laos: 'LA',
  latvia: 'LV',
  lebanon: 'LB',
  lesotho: 'LS',
  liberia: 'LR',
  libya: 'LY',
  liechtenstein: 'LI',
  lithuania: 'LT',
  luxembourg: 'LU',
  madagascar: 'MG',
  malawi: 'MW',
  malaysia: 'MY',
  maldives: 'MV',
  mali: 'ML',
  malta: 'MT',
  'marshall islands': 'MH',
  mauritania: 'MR',
  mauritius: 'MU',
  mexico: 'MX',
  micronesia: 'FM',
  moldova: 'MD',
  monaco: 'MC',
  mongolia: 'MN',
  montenegro: 'ME',
  morocco: 'MA',
  mozambique: 'MZ',
  myanmar: 'MM',
  namibia: 'NA',
  nauru: 'NR',
  nepal: 'NP',
  netherlands: 'NL',
  'new zealand': 'NZ',
  nicaragua: 'NI',
  niger: 'NE',
  nigeria: 'NG',
  'north korea': 'KP',
  'north macedonia': 'MK',
  norway: 'NO',
  oman: 'OM',
  pakistan: 'PK',
  palau: 'PW',
  panama: 'PA',
  'papua new guinea': 'PG',
  paraguay: 'PY',
  peru: 'PE',
  philippines: 'PH',
  poland: 'PL',
  portugal: 'PT',
  qatar: 'QA',
  romania: 'RO',
  russia: 'RU',
  rwanda: 'RW',
  'saint kitts and nevis': 'KN',
  'saint lucia': 'LC',
  'saint vincent and the grenadines': 'VC',
  samoa: 'WS',
  'san marino': 'SM',
  'sao tome and principe': 'ST',
  'saudi arabia': 'SA',
  senegal: 'SN',
  serbia: 'RS',
  seychelles: 'SC',
  'sierra leone': 'SL',
  singapore: 'SG',
  slovakia: 'SK',
  slovenia: 'SI',
  'solomon islands': 'SB',
  somalia: 'SO',
  'south africa': 'ZA',
  'south korea': 'KR',
  'south sudan': 'SS',
  spain: 'ES',
  'sri lanka': 'LK',
  sudan: 'SD',
  suriname: 'SR',
  sweden: 'SE',
  switzerland: 'CH',
  syria: 'SY',
  taiwan: 'TW',
  tajikistan: 'TJ',
  tanzania: 'TZ',
  thailand: 'TH',
  'timor leste': 'TL',
  togo: 'TG',
  tonga: 'TO',
  'trinidad and tobago': 'TT',
  tunisia: 'TN',
  turkey: 'TR',
  turkmenistan: 'TM',
  tuvalu: 'TV',
  uganda: 'UG',
  ukraine: 'UA',
  'united arab emirates': 'AE',
  'united kingdom': 'GB',
  'united states': 'US',
  'united states of america': 'US',
  uruguay: 'UY',
  uzbekistan: 'UZ',
  vanuatu: 'VU',
  'vatican city': 'VA',
  venezuela: 'VE',
  vietnam: 'VN',
  yemen: 'YE',
  zambia: 'ZM',
  zimbabwe: 'ZW',
  usa: 'US',
  'u s a': 'US',
  uk: 'GB',
  'u k': 'GB',
  'ivory coast': 'CI',
  'cape verde': 'CV',
  'viet nam': 'VN',
  macedonia: 'MK',
};

const normalizeCountryName = (value: string): string => {
  const normalized = typeof value.normalize === 'function' ? value.normalize('NFD') : value;
  return normalized
    .toLowerCase()
    .replace(DIACRITIC_REGEX, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
};

let cachedCountryNameToCode: Map<string, string> | null = null;

const getCountryNameToCodeMap = (): Map<string, string> => {
  if (cachedCountryNameToCode) return cachedCountryNameToCode;
  const map = new Map<string, string>();
  try {
    if (typeof Intl === 'undefined') return map;
    const intlAny = Intl as unknown as {
      DisplayNames?: new (locales: string[], options: { type: string }) => { of: (code: string) => string | undefined };
      supportedValuesOf?: (type: string) => string[];
    };

    if (!intlAny.DisplayNames) return map;
    const displayNames = new intlAny.DisplayNames(['en'], { type: 'region' });

    const codes =
      typeof intlAny.supportedValuesOf === 'function'
        ? intlAny.supportedValuesOf('region').filter(code => /^[A-Z]{2}$/.test(code))
        : [];

    for (const code of codes) {
      const name = displayNames.of(code);
      if (!name) continue;
      map.set(normalizeCountryName(name), code);
    }
  } catch {
    return map;
  }

  cachedCountryNameToCode = map;
  return map;
};

const getFlagEmojiFromCountryCode = (code: string): string => {
  if (typeof String.fromCodePoint !== 'function') return '';
  return code
    .toUpperCase()
    .replace(/[A-Z]/g, char => String.fromCodePoint(127397 + char.charCodeAt(0)));
};

const getFlagEmojiFromCountryName = (name: string): string | null => {
  const normalized = normalizeCountryName(name);
  const code = COUNTRY_ALIASES[normalized] ?? getCountryNameToCodeMap().get(normalized);
  if (!code) return null;
  const flag = getFlagEmojiFromCountryCode(code);
  return flag || null;
};

export const formatLocationWithFlag = (location: string): string => {
  if (!location) return location;
  if (FLAG_EMOJI_REGEX.test(location)) return location;

  const parts = location.split(',').map(part => part.trim()).filter(Boolean);
  if (parts.length < 2) return location;

  const country = parts[parts.length - 1];
  const flag = getFlagEmojiFromCountryName(country);
  if (!flag) return location;

  const city = parts.slice(0, -1).join(', ');
  return `${city}, ${country} ${flag}`;
};
