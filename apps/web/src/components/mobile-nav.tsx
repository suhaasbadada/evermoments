"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Brain, Home, Mic, Search } from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/record", label: "Record", icon: Mic },
  { href: "/ask", label: "Ask", icon: Search },
  { href: "/memories", label: "Memories", icon: BookOpen },
  { href: "/practice", label: "Practice", icon: Brain },
];

export function MobileNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="fixed bottom-3 left-1/2 z-40 w-[min(28rem,calc(100%-1rem))] -translate-x-1/2"
    >
      <div className="app-card flex items-center justify-between rounded-2xl px-2 py-1.5">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`app-button flex min-w-[3.2rem] flex-col items-center gap-1 rounded-xl px-2 py-1.5 text-[10px] transition-colors ${
                isActive
                  ? "bg-teal-600 text-white shadow-sm"
                  : "text-teal-900/65 hover:bg-white/70"
              }`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
