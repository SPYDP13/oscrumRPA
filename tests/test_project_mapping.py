from taskRefinings.projectMapping import format_mapping, group_of, parse_mapping, resolve, rules_from_projects


def test_parse_et_format():
    rules = parse_mapping(" miniapp/*=12 ; 406=34;;invalide;\norange/ompi = 56")
    assert rules == [("miniapp/*", "12"), ("406", "34"), ("orange/ompi", "56")]
    assert parse_mapping(format_mapping(rules)) == rules


def test_priorite_id_puis_chemin_puis_motif_le_plus_long():
    rules = parse_mapping("miniapp/*=1;miniapp/pay/*=2;miniapp/pay/core=3;77=4")
    assert resolve(rules, "10", "miniapp/home") == "1"
    assert resolve(rules, "11", "miniapp/pay/front") == "2"       # motif le plus long
    assert resolve(rules, "12", "miniapp/pay/core") == "3"        # chemin exact
    assert resolve(rules, "77", "miniapp/pay/core") == "4"        # id exact
    assert resolve(rules, "13", "Miniapp/Home") == "1"            # casse ignorée
    assert resolve(rules, "14", "autre/depot") is None
    assert resolve(rules, "14", "") is None


def test_motif_couvre_les_sous_groupes():
    assert resolve(parse_mapping("miniapp/*=1"), "1", "miniapp/sous/groupe/depot") == "1"


def test_migration_ancienne_configuration():
    assert rules_from_projects([("406", "preprod"), ("406", "develop"), ("404", "")], "9") == [("406", "9"), ("404", "9")]
    assert rules_from_projects([("406", "preprod")], None) == []


def test_group_of():
    assert group_of("a/b/depot") == "a/b"
    assert group_of("depot") == ""
