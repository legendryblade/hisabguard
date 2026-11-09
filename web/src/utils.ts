import type { TripDetail } from './types.ts';

export function money(value: string | null | undefined): string {
  if (value == null || !/^-?\d+\.\d{2}$/.test(value)) return 'Not recorded';
  const [whole, fraction] = value.split('.');
  return `BDT ${whole!.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction}`;
}

export function decimalInput(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d+(?:\.\d{1,2})?$/.test(trimmed)) throw new Error('Amount must be a non-negative decimal with at most two decimal places, for example 3500.00.');
  const [whole, fraction = ''] = trimmed.split('.');
  return `${whole!.replace(/^0+(?=\d)/, '')}.${fraction.padEnd(2, '0')}`;
}

export function errorDetail(value: unknown): string {
  if (typeof value === 'string' && value.trim()) return value;
  if (Array.isArray(value)) {
    const messages = value.map((item: unknown) => {
      if (!item || typeof item !== 'object') return '';
      const entry = item as Record<string, unknown>;
      const loc = Array.isArray(entry.loc) ? entry.loc.filter((part) => typeof part === 'string' || typeof part === 'number').filter((part) => part !== 'body').join(' / ') : '';
      return typeof entry.msg === 'string' ? `${loc ? `${loc}: ` : ''}${entry.msg}` : '';
    }).filter(Boolean);
    if (messages.length) return messages.join('; ');
  }
  return 'The request could not be completed. Please retry.';
}

export function latestRun(detail: TripDetail) {
  return detail.investigations.reduce<TripDetail['investigations'][number] | undefined>((latest, run) => !latest || run.id > latest.id ? run : latest, undefined);
}

export function canClose(detail: TripDetail): boolean {
  const run = latestRun(detail);
  return detail.trip.status !== 'settled' && detail.settlement.can_settle && run?.status === 'completed' && run.revision === detail.trip.revision;
}

export function label(value: string): string {
  return value.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase());
}

export function dateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
}

export function jsonText(value: unknown): string {
  return JSON.stringify(value, null, 2) ?? 'No details recorded';
}
