from app.common import split_sql


def test_split_keeps_dollar_blocks():
    sql = "select ';'; -- c;\nDO $$ BEGIN PERFORM 1; END $$; VACUUM t;"
    assert split_sql(sql) == ["select ';'", "DO $$ BEGIN PERFORM 1; END $$", "VACUUM t"]


def test_split_all_scenarios():
    import glob
    for f in glob.glob("scenarios/*.sql"):
        assert split_sql(open(f, encoding="utf-8").read()), f
