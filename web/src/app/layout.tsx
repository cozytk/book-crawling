import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "갈피 · 책 평점 비교",
  description: "여러 플랫폼의 책 평점을 한눈에 비교하세요",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <a href="#main" className="skip-link">본문으로 건너뛰기</a>
        <header className="site-header"><div className="header-inner">
          <Link href="/" className="brand" aria-label="갈피 홈"><svg width="28" height="32" viewBox="0 0 28 32" fill="none" aria-hidden="true"><path d="M4 3h20v26l-10-6-10 6V3Z" fill="currentColor" /><path d="M9 10h10M9 14h7" stroke="#fffaf4" strokeWidth="1.5" /></svg><strong>갈피</strong><span>책 평점 비교</span></Link>
          <nav aria-label="주 메뉴"><Link href="/">책 찾기</Link><Link href="/bookmarks">읽을 책</Link><Link href="/history">검색 기록</Link></nav>
        </div></header>
        <main id="main" className="site-main">{children}</main>
        <footer className="site-footer"><span>갈피</span><p>다음 한 권을 고르는 작은 단서.</p><span className="footer-caption">BOOK CRAWLER</span></footer>
      </body>
    </html>
  );
}
