const LOCALE = "en-GB";
const EMPTY = "n/a";

const compactMoney = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 1,
});
const fullMoney = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});
const wholeNumber = new Intl.NumberFormat(LOCALE);
const monthLabel = new Intl.DateTimeFormat(LOCALE, { month: "short", timeZone: "UTC" });
const monthYearLabel = new Intl.DateTimeFormat(LOCALE, {
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});
const syncedLabel = new Intl.DateTimeFormat(LOCALE, {
  dateStyle: "medium",
  timeStyle: "short",
});

const isNumber = (value) => typeof value === "number" && Number.isFinite(value);

export const money = (value) => (isNumber(value) ? compactMoney.format(value) : EMPTY);
export const moneyFull = (value) => (isNumber(value) ? fullMoney.format(value) : EMPTY);
export const count = (value) => (isNumber(value) ? wholeNumber.format(value) : EMPTY);
export const percent = (value) => (isNumber(value) ? `${Math.round(value * 100)}%` : EMPTY);
export const days = (value) => (isNumber(value) ? `${count(value)} days` : EMPTY);
export const plural = (value, noun) => `${count(value)} ${noun}${value === 1 ? "" : "s"}`;

const monthDate = (key) => new Date(`${key}-01T00:00:00Z`);
export const shortMonth = (key) => monthLabel.format(monthDate(key));
export const longMonth = (key) => monthYearLabel.format(monthDate(key));

export function synced(isoString) {
  const date = new Date(isoString);
  return Number.isNaN(date.getTime()) ? "Sync time unknown" : `Synced ${syncedLabel.format(date)}`;
}
