import type { AnchorHTMLAttributes, ReactNode } from "react";
import { navigate } from "../router";

type Props = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string | { pathname: string }; children?: ReactNode; prefetch?: boolean };

export default function Link({ href, children, onClick, prefetch: _p, ...rest }: Props) {
  const to = typeof href === "string" ? href : href.pathname;
  return (
    <a
      {...rest}
      href={to}
      onClick={(e) => {
        onClick?.(e);
        if (e.defaultPrevented || /^https?:/.test(to)) return;
        e.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}
