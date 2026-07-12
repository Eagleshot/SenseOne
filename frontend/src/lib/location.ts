import { UNAVAILABLE_LABEL } from '@/lib/placeholders';

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

// The distinct ISO 3166-1 alpha-2 codes from the curated alias map above —
// the single source of which countries exist here. (Intl.supportedValuesOf has
// no 'region' key, so the code list cannot come from Intl.)
const COUNTRY_CODES: string[] = Array.from(new Set(Object.values(COUNTRY_ALIASES)));

// English display names per code via Intl.DisplayNames, with a title-cased
// alias key as fallback for engines without DisplayNames. The first alias for
// a code is its canonical long name (shorthands like 'usa' come later).
const getEnglishCountryNames = (): Map<string, string> => {
  const names = new Map<string, string>();
  for (const [alias, code] of Object.entries(COUNTRY_ALIASES)) {
    if (!names.has(code)) {
      names.set(code, alias.replace(/(?:^|\s)[a-z]/g, char => char.toUpperCase()));
    }
  }
  try {
    if (typeof Intl !== 'undefined' && (Intl as { DisplayNames?: unknown }).DisplayNames) {
      const displayNames = new Intl.DisplayNames(['en'], { type: 'region' });
      for (const code of COUNTRY_CODES) {
        const name = displayNames.of(code);
        if (name && name !== code) names.set(code, name);
      }
    }
  } catch {
    // Keep the alias-derived fallback names.
  }
  return names;
};

let cachedCountryNameToCode: Map<string, string> | null = null;

const getCountryNameToCodeMap = (): Map<string, string> => {
  if (cachedCountryNameToCode) return cachedCountryNameToCode;
  const map = new Map<string, string>();
  // Map the display names back to codes so a value picked from the dropdown
  // (e.g. 'Czechia') resolves even when the alias list spells it differently.
  for (const [code, name] of getEnglishCountryNames()) {
    map.set(normalizeCountryName(name), code);
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

export const getFlagEmojiFromCountryName = (name: string): string | null => {
  const normalized = normalizeCountryName(name);
  const code = COUNTRY_ALIASES[normalized] ?? getCountryNameToCodeMap().get(normalized);
  if (!code) return null;
  const flag = getFlagEmojiFromCountryCode(code);
  return flag || null;
};

export type CountryOption = { code: string; name: string; flag: string };

let cachedCountryOptions: CountryOption[] | null = null;

// Full list of countries (English display names + flag), sorted by name, for
// populating a country dropdown. Codes come from the curated alias map; names
// from Intl.DisplayNames where available.
export const getCountryOptions = (): CountryOption[] => {
  if (cachedCountryOptions) return cachedCountryOptions;
  const options = Array.from(getEnglishCountryNames(), ([code, name]) => ({
    code,
    name,
    flag: getFlagEmojiFromCountryCode(code),
  }));
  options.sort((a, b) => a.name.localeCompare(b.name));
  cachedCountryOptions = options;
  return options;
};

/** English display name for an ISO country code (matching the dropdown
 * options), or null for codes outside the curated list. */
export const getCountryNameFromCode = (code: string): string | null =>
  getCountryOptions().find(option => option.code === code.toUpperCase())?.name ?? null;

export const formatLocationWithFlag = (
  location: string,
  country?: string | null,
  countryEmoji?: string | null
): string => {
  const normalizedLocation = location.trim();
  if (!normalizedLocation) return UNAVAILABLE_LABEL;
  if (FLAG_EMOJI_REGEX.test(normalizedLocation)) return normalizedLocation;

  const normalizedCountry = country?.trim() ?? "";
  const normalizedEmoji = countryEmoji?.trim() ?? "";

  if (normalizedCountry) {
    const suffix = normalizedEmoji || getFlagEmojiFromCountryName(normalizedCountry) || "";
    return suffix ? `${normalizedLocation}, ${normalizedCountry} ${suffix}` : `${normalizedLocation}, ${normalizedCountry}`;
  }

  const parts = normalizedLocation.split(',').map(part => part.trim()).filter(Boolean);
  if (parts.length < 2) return normalizedLocation;

  const fallbackCountry = parts[parts.length - 1];
  const flag = getFlagEmojiFromCountryName(fallbackCountry);
  if (!flag) return normalizedLocation;

  const city = parts.slice(0, -1).join(', ');
  return `${city}, ${fallbackCountry} ${flag}`;
};

