"use client";
import { useEffect } from "react";
import { useAcademy } from "@/lib/store/storage";

/** Applies theme + motion settings to <html>. "system" follows prefers-color-scheme live. */
export function ThemeSync() {
  const { settings } = useAcademy();
  useEffect(() => {
    const root = document.documentElement;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const apply = () => {
      const theme = settings.theme === "system" ? (mq.matches ? "light" : "dark") : settings.theme;
      root.dataset.theme = theme;
    };
    apply();
    root.dataset.motion = settings.motion;
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [settings.theme, settings.motion]);
  return null;
}

/** Inline, render-blocking snippet that avoids a theme flash before hydration. */
export const themeBootScript = `try{var s=JSON.parse(localStorage.getItem("setter-os-academy:v1")||"{}").settings||{};var t=s.theme||"dark";if(t==="system"){t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.dataset.theme=t;if(s.motion)document.documentElement.dataset.motion=s.motion}catch(e){}`;
