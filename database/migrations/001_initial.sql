-- Applied automatically only when the PostgreSQL volume is first initialized.
BEGIN;
CREATE TABLE courses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (length(btrim(name)) > 0),
    semester_name text NOT NULL CHECK (length(btrim(semester_name)) > 0),
    starts_on date NOT NULL,
    ends_on date NOT NULL CHECK (ends_on >= starts_on),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE class_meetings (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id bigint NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    weekday smallint NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    starts_at time NOT NULL,
    ends_at time NOT NULL CHECK (ends_at > starts_at),
    location text,
    UNIQUE (course_id, weekday, starts_at)
);

CREATE TABLE tasks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL CHECK (length(btrim(title)) > 0),
    description text,
    planned_on date,
    due_on date,
    due_time time CHECK (due_time IS NULL OR due_on IS NOT NULL),
    status text NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo', 'in_progress', 'done')),
    course_id bigint REFERENCES courses(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    CHECK ((status = 'done') = (completed_at IS NOT NULL))
);

CREATE INDEX class_meetings_weekday_idx ON class_meetings (weekday, starts_at);
CREATE INDEX tasks_open_planned_idx ON tasks (planned_on) WHERE status <> 'done';
CREATE INDEX tasks_open_due_idx ON tasks (due_on) WHERE status <> 'done';
CREATE INDEX tasks_course_idx ON tasks (course_id);

CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;
CREATE TRIGGER courses_updated BEFORE UPDATE ON courses
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER tasks_updated BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
COMMIT;
