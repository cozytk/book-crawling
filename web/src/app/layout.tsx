import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Book Crawler - 책 평점 비교",
  description: "여러 플랫폼의 책 평점을 한눈에 비교하세요",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="bg-gray-50 text-gray-900 min-h-screen antialiased">
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
            <div>
              <a href="/" className="text-xl font-bold tracking-tight">
                Book Crawler
              </a>
              <span className="ml-2 text-sm text-gray-500">
                책 평점 비교
              </span>
            </div>
            <nav>
              <a
                href="/history"
                className="text-sm text-gray-600 hover:text-gray-900 transition-colors"
              >
                검색 히스토리
              </a>
            </nav>
          </div>
        </header>
        <main className="max-w-4xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
