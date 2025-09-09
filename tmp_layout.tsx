import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import ResetHiddenButton from "@/components/ResetHiddenButton";

export const metadata: Metadata = {
  title: "繝｡繧､繝励Ν縺ｮ豁ｴ蜿ｲ | Maple Chronicle",
  description: "2003-2009縺ｮ窶懊≠縺ｮ鬆・昴ｒ蟷ｴ陦ｨ縺ｨ逕ｨ隱槭〒霎ｿ繧・,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <header className="container header ms-woodbar">
          <div className="brand">
            <Link href="/history">Maple Chronicle</Link>
          </div>
          <nav className="nav">
            <Link href="/history">蟷ｴ陦ｨ</Link>
            <Link href="/history/glossary">縺ゅｋ縺ゅｋ霎槫・</Link>
          </nav>
        </header>
        <main className="container">{children}</main>
        <footer className="container footer">
          <div className="links">
            <Link href="/faq">繧医￥縺ゅｋ雉ｪ蝠・/Link>
            <Link href="/terms">蛻ｩ逕ｨ隕冗ｴ・/Link>
            <Link href="/privacy">繝励Λ繧､繝舌す繝ｼ</Link>
            <Link href="/contact">縺雁撫蜷医○</Link>
          </div>
          <ResetHiddenButton />
        </footer>
      </body>
    </html>
  );
}


