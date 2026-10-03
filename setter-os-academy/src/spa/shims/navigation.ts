import { back, navigate, useLocation } from "../router";

export function useRouter() {
  return { push: (to: string) => navigate(to), replace: (to: string) => navigate(to, true), back, refresh: () => {}, prefetch: () => {} };
}
export function usePathname(): string {
  return useLocation().split("?")[0] ?? "/";
}
export function useSearchParams(): URLSearchParams {
  return new URLSearchParams(useLocation().split("?")[1] ?? "");
}
