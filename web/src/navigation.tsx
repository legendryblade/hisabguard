import { useSyncExternalStore } from 'react';
import type { AnchorHTMLAttributes } from 'react';

function subscribe(listener: () => void) {
  window.addEventListener('popstate', listener);
  window.addEventListener('hisabguard:navigate', listener);
  return () => { window.removeEventListener('popstate', listener); window.removeEventListener('hisabguard:navigate', listener); };
}
export function usePath() { return useSyncExternalStore(subscribe, () => window.location.pathname); }
export function navigate(path: string) {
  // Only internal absolute paths are accepted; no user-supplied redirect targets.
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) throw new Error('Invalid local route');
  window.history.pushState(null, '', path);
  window.dispatchEvent(new Event('hisabguard:navigate'));
}
export function Link({ href = '/', onClick, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a {...props} href={href} onClick={(event) => {
    onClick?.(event);
    if (!event.defaultPrevented && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.altKey && !event.shiftKey && !props.target) {
      event.preventDefault(); navigate(href);
    }
  }} />;
}
