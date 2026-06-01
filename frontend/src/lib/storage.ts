const canUseStorage = () => typeof window !== "undefined" && typeof window.localStorage !== "undefined";

const readStoredValue = (key: string) => {
  if (!canUseStorage()) return null;

  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

/** Generic getter with optional parsing. */
export const getStored = <T = string>(
  key: string,
  fallback: T,
  parse?: (value: string) => T
): T => {
  const value = readStoredValue(key);
  if (value === null) return fallback;
  return parse ? parse(value) : (value as T);
};

export const getStoredString = (key: string, fallback: string) => getStored(key, fallback);

export const getStoredOptionalString = (key: string) => readStoredValue(key);

const writeStoredValue = (key: string, value: string | null) => {
  if (!canUseStorage()) return;

  try {
    if (value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Ignore storage failures
  }
};

export const setStoredString = (key: string, value: string) => {
  writeStoredValue(key, value);
};

export const setStoredBoolean = (key: string, value: boolean) => {
  setStoredString(key, String(value));
};

export const setStoredOptionalString = (key: string, value: string | null) => {
  writeStoredValue(key, value);
};

