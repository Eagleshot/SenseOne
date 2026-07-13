const canUseStorage = () => typeof window !== "undefined" && typeof window.localStorage !== "undefined";

const readStoredValue = (key: string) => {
  if (!canUseStorage()) return null;

  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
};

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

export const setStoredOptionalString = (key: string, value: string | null) => {
  writeStoredValue(key, value);
};

