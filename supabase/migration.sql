-- Book Crawler: Supabase 스키마

-- searches: 검색 기록 + 캐싱
CREATE TABLE searches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query TEXT NOT NULL,
  avg_rating FLOAT,
  total_reviews INT DEFAULT 0,
  platform_count INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_searches_query ON searches(query);
CREATE INDEX idx_searches_created_at ON searches(created_at DESC);

-- platform_ratings: 플랫폼별 결과
CREATE TABLE platform_ratings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  search_id UUID REFERENCES searches(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,
  rating FLOAT,
  rating_scale INT NOT NULL,
  normalized_rating FLOAT,
  review_count INT DEFAULT 0,
  book_title TEXT,
  url TEXT,
  crawled_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ratings_search_id ON platform_ratings(search_id);

-- RLS (Row Level Security) - 공개 읽기 허용
ALTER TABLE searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_ratings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access" ON searches FOR SELECT USING (true);
CREATE POLICY "Service insert access" ON searches FOR INSERT WITH CHECK (true);

CREATE POLICY "Public read access" ON platform_ratings FOR SELECT USING (true);
CREATE POLICY "Service insert access" ON platform_ratings FOR INSERT WITH CHECK (true);
