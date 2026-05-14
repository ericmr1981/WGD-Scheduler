-- WGD-Scheduler 数据库建表脚本
-- 用于 Supabase SQL 编辑器执行

-- 门店表
CREATE TABLE IF NOT EXISTS stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    open_time TIME NOT NULL DEFAULT '10:00',
    close_time TIME NOT NULL DEFAULT '22:00',
    employee_count INTEGER NOT NULL DEFAULT 3,
    service_type TEXT NOT NULL DEFAULT '纯堂食',
    productivity_per_hour INTEGER NOT NULL DEFAULT 18,
    base_daily_customers INTEGER NOT NULL DEFAULT 200,
    peak_customers_per_hour INTEGER NOT NULL DEFAULT 60,
    weekday_lunch_peak TEXT NOT NULL DEFAULT '12:00-14:00',
    weekday_dinner_peak TEXT NOT NULL DEFAULT '17:00-19:00',
    weekend_lunch_peak TEXT NOT NULL DEFAULT '11:00-14:00',
    weekend_dinner_peak TEXT NOT NULL DEFAULT '16:00-20:00',
    opening_prep_mins INTEGER NOT NULL DEFAULT 60,
    closing_tasks_mins INTEGER NOT NULL DEFAULT 60,
    meal_break_mins INTEGER NOT NULL DEFAULT 30,
    max_meals_per_employee INTEGER NOT NULL DEFAULT 1,
    target_hours_per_employee NUMERIC(4,1) NOT NULL DEFAULT 8.0,
    min_staff_on_duty INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 员工表
CREATE TABLE IF NOT EXISTS employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 排班方案表
CREATE TABLE IF NOT EXISTS schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 排班明细表
CREATE TABLE IF NOT EXISTS schedule_shifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    shift_type TEXT NOT NULL CHECK (shift_type IN ('A', 'B', 'C', '休息')),
    role TEXT,
    CONSTRAINT unique_employee_date UNIQUE (employee_id, date)
);

-- 复盘记录表
CREATE TABLE IF NOT EXISTS weekly_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    actual_customers INTEGER NOT NULL DEFAULT 0,
    actual_staff_hours FLOAT NOT NULL DEFAULT 0,
    actual_peak_queue_time INTEGER NOT NULL DEFAULT 0,
    adjusted_productivity FLOAT,
    issues TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Row Level Security（公开读写，MVP 阶段够用）───────────
-- 如需后续接入 Supabase Auth，再改为 authenticated 策略

ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "public_read_write" ON stores FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "public_read_write" ON employees FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "public_read_write" ON schedules FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE schedule_shifts ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "public_read_write" ON schedule_shifts FOR ALL USING (true) WITH CHECK (true);

ALTER TABLE weekly_reviews ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "public_read_write" ON weekly_reviews FOR ALL USING (true) WITH CHECK (true);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_employees_store ON employees(store_id);
CREATE INDEX IF NOT EXISTS idx_schedules_store ON schedules(store_id);
CREATE INDEX IF NOT EXISTS idx_schedule_shifts_schedule ON schedule_shifts(schedule_id);
CREATE INDEX IF NOT EXISTS idx_weekly_reviews_store ON weekly_reviews(store_id);
