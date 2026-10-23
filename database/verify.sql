\set ON_ERROR_STOP on
-- Synthetic data only; the complete verification is rolled back.
BEGIN;
DO $$
DECLARE cid bigint; tid bigint;
BEGIN
    INSERT INTO courses(name, semester_name, starts_on, ends_on)
        VALUES ('verification', 'synthetic', '2026-09-01', '2026-12-31') RETURNING id INTO cid;
    INSERT INTO class_meetings(course_id, weekday, starts_at, ends_at, location)
        VALUES (cid, 1, '09:00', '10:00', 'synthetic');
    INSERT INTO tasks(title, course_id, due_on, due_time)
        VALUES ('verification', cid, '2026-10-24', '18:00') RETURNING id INTO tid;
    UPDATE tasks SET status = 'done', completed_at = now() WHERE id = tid;
    BEGIN
        INSERT INTO class_meetings(course_id, weekday, starts_at, ends_at)
            VALUES (cid, 8, '09:00', '10:00');
        RAISE EXCEPTION 'invalid weekday accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO class_meetings(course_id, weekday, starts_at, ends_at)
            VALUES (cid, 2, '10:00', '09:00');
        RAISE EXCEPTION 'invalid meeting range accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO tasks(title) VALUES ('   ');
        RAISE EXCEPTION 'blank title accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO tasks(title, status) VALUES ('invalid', 'unknown');
        RAISE EXCEPTION 'unknown task status accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO courses(name, semester_name, starts_on, ends_on)
            VALUES ('invalid', 'synthetic', '2026-12-31', '2026-09-01');
        RAISE EXCEPTION 'invalid semester accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO tasks(title, due_time) VALUES ('invalid', '18:00');
        RAISE EXCEPTION 'time without date accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO tasks(title, status) VALUES ('invalid', 'done');
        RAISE EXCEPTION 'completed task without timestamp accepted';
    EXCEPTION WHEN check_violation THEN NULL; END;
    BEGIN
        INSERT INTO tasks(title, course_id) VALUES ('invalid', -1);
        RAISE EXCEPTION 'invalid reference accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL; END;
    DELETE FROM courses WHERE id = cid;
    IF EXISTS (SELECT 1 FROM class_meetings WHERE course_id = cid)
        OR EXISTS (SELECT 1 FROM tasks WHERE id = tid AND course_id IS NOT NULL) THEN
        RAISE EXCEPTION 'reference deletion behavior failed';
    END IF;
END;
$$;
ROLLBACK;
