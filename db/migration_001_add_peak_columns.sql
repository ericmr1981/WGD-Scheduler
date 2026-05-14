-- 迁移脚本：给 stores 表添加高峰时段字段
-- 在 Supabase SQL Editor 中执行

ALTER TABLE stores ADD COLUMN IF NOT EXISTS weekday_lunch_peak TEXT NOT NULL DEFAULT '12:00-14:00';
ALTER TABLE stores ADD COLUMN IF NOT EXISTS weekday_dinner_peak TEXT NOT NULL DEFAULT '17:00-19:00';
ALTER TABLE stores ADD COLUMN IF NOT EXISTS weekend_lunch_peak TEXT NOT NULL DEFAULT '11:00-14:00';
ALTER TABLE stores ADD COLUMN IF NOT EXISTS weekend_dinner_peak TEXT NOT NULL DEFAULT '16:00-20:00';
