ALTER TABLE tf_profiles
  ADD COLUMN gender VARCHAR(20) NOT NULL DEFAULT 'keine Angabe',
  ADD COLUMN qualification VARCHAR(40) NOT NULL DEFAULT 'Strecken-TF',
  ADD COLUMN weekly_hours_minutes INTEGER NOT NULL DEFAULT 2400,
  ADD COLUMN joined_on DATE NULL,
  ADD COLUMN bahncard_valid_until DATE NULL,
  ADD COLUMN photo_placeholder VARCHAR(40) NOT NULL DEFAULT 'Bild folgt';
