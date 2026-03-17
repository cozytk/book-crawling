export interface Bookmark {
  searchId: string;
  query: string;
  avgRating: number | null;
  totalReviews: number;
  platformCount: number;
  bookmarkedAt: string;
}

const STORAGE_KEY = "book-crawler-bookmarks";

function load(): Bookmark[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function save(bookmarks: Bookmark[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
}

export function getBookmarks(): Bookmark[] {
  return load();
}

export function isBookmarked(searchId: string): boolean {
  return load().some((b) => b.searchId === searchId);
}

export function addBookmark(bookmark: Bookmark): void {
  const list = load();
  if (list.some((b) => b.searchId === bookmark.searchId)) return;
  list.unshift(bookmark);
  save(list);
}

export function removeBookmark(searchId: string): void {
  save(load().filter((b) => b.searchId !== searchId));
}

export function toggleBookmark(bookmark: Bookmark): boolean {
  if (isBookmarked(bookmark.searchId)) {
    removeBookmark(bookmark.searchId);
    return false;
  }
  addBookmark(bookmark);
  return true;
}
