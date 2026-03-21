const canUseStorage = () => typeof window !== "undefined" && typeof window.localStorage !== "undefined";

const readStoredValue = (key: string) => {
  if (!canUseStorage()) return null;

  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

export const getStoredString = (key: string, fallback: string) => readStoredValue(key) ?? fallback;

export const getStoredOptionalString = (key: string) => readStoredValue(key);

export const getStoredBoolean = (key: string, fallback: boolean) => {
  const storedValue = readStoredValue(key);
  return storedValue === null ? fallback : storedValue === "true";
};

export const setStoredString = (key: string, value: string) => {
  if (!canUseStorage()) return;

  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore storage write failures and keep the in-memory state.
  }
};

export const setStoredBoolean = (key: string, value: boolean) => {
  setStoredString(key, String(value));
};

export const setStoredOptionalString = (key: string, value: string | null) => {
  if (value === null) {
    removeStoredValue(key);
    return;
  }

  setStoredString(key, value);
};

export const removeStoredValue = (key: string) => {
  if (!canUseStorage()) return;

  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore storage removal failures and keep rendering.
  }
};
