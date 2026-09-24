"""固定间隔车队首车发车区间的单元测试（含逐秒暴力对照）。"""

import random

from app.greenwave import compute_convoy_starts


def it(name=None, **kw):
    # 默认 green_start == green_end 表示整周期常绿，所有取值均满足 schema 约束。
    return {
        "cycle": 60,
        "offset": 0,
        "green_start": 0,
        "green_end": 0,
        "travel": 0,
        **kw,
    }


def test_convoy_single_intersection_basic():
    # 绿灯 [0,30) 周期 60，3 辆车、间隔 10：
    # 单车可行窗口 [0,30) [60,90)，首车范围 [0, 200)（末车 t+20 < 220）。
    # j=0: [0,30) [60,90) [120,150) [180,200)
    # j=1 左移 10: [-10,20) [50,80) [110,140) [170,200)
    # j=2 左移 20: [-20,10) [40,70) [100,130) [160,190)
    # 三者逐周期交集：[0,10) [60,70) [120,130) [180,190)
    node = it(cycle=60, green_start=0, green_end=30, travel=0)
    assert compute_convoy_starts([node], 0, 220, 3, 10) == [
        [0, 10],
        [60, 70],
        [120, 130],
        [180, 190],
    ]


def test_convoy_two_vehicles_window_shrinks_at_both_ends():
    # 绿灯 [0,30) 周期 60，2 辆车、间隔 10：每段可行首车区间由 30 秒缩为 20 秒。
    node = it(cycle=60, green_start=0, green_end=30, travel=0)
    assert compute_convoy_starts([node], 0, 120, 2, 10) == [
        [0, 20],
        [60, 80],
    ]


def test_convoy_must_check_all_vehicles_not_only_first_and_last():
    # 单路口、周期 20、绿灯 [0,8)，3 辆车、间隔 7，范围 [0,60)。
    # 首车 t=6 时三辆车本地相位为 6（绿）、13（红）、20≡0（绿）：
    # 首车与末车都遇绿、只有中车遇红——只查首末车会错误放行 t∈[6,8)、
    # [26,28) 等区间，逐车求交后全部被剔除，整体无解。
    node = it(cycle=20, green_start=0, green_end=8, travel=0)
    assert compute_convoy_starts([node], 0, 60, 3, 7) == []


def test_convoy_disjoint_intersections_no_solution():
    # 两路口绿灯 [0,10) 与 [20,30)（同为周期 30、无偏移）：单车窗口本就不
    # 相交，任何车队都无解。
    nodes = [
        it(cycle=30, green_start=0, green_end=10, travel=0),
        it(cycle=30, green_start=20, green_end=30, travel=0),
    ]
    assert compute_convoy_starts(nodes, 0, 120, 2, 10) == []
    assert compute_convoy_starts(nodes, 0, 120, 3, 10) == []


def test_convoy_multi_intersection_band_with_interval_gap():
    # 两路口可行窗口重合为 [0,30) 周期 60（下游 offset=30 补偿 30 秒行程）。
    # 2 辆车、间隔 10、范围 [0,200)，首车范围 [0,190)：
    # 每段可行首车区间两端各被压 10 秒：[0,20) [60,80) [120,140) [180,190)。
    nodes = [
        it(cycle=60, offset=0, green_start=0, green_end=30, travel=0),
        it(cycle=60, offset=30, green_start=0, green_end=30, travel=30),
    ]
    assert compute_convoy_starts(nodes, 0, 200, 2, 10) == [
        [0, 20],
        [60, 80],
        [120, 140],
        [180, 190],
    ]


def test_convoy_wrapping_green_window_shift():
    # 跨零点绿灯 [50,60)∪[0,10)、行驶 5：单车窗口（范围 [0,130)）为
    # [0,5) [45,65) [105,125)。2 辆车间隔 10、首车范围 [0,120)：
    # W 与 W-10 取交，[0,5) 段与 [-10,-5) 无交被丢弃，其余各段缩为 10 秒。
    node = it(cycle=60, green_start=50, green_end=10, travel=5)
    assert compute_convoy_starts([node], 0, 130, 2, 10) == [
        [45, 55],
        [105, 115],
    ]


def test_convoy_travel_max_fluctuation_erodes_windows():
    # 绿灯 [20,40)、行驶 [0,10]：单车窗口收缩为 [20,30) 周期 60。
    # 2 辆车间隔 5：可行首车区间再缩为 [20,25) 周期 60。
    node = it(
        cycle=60, green_start=20, green_end=40, travel=0, travel_max=10
    )
    assert compute_convoy_starts([node], 0, 180, 2, 5) == [
        [20, 25],
        [80, 85],
        [140, 145],
    ]


def test_convoy_always_green_intersection_only_bounds_by_range():
    # 整周期常绿：唯一约束是全部车辆落在发车范围内 ⇔ 首车整段可行。
    nodes = [it(travel=i * 7) for i in range(4)]
    assert compute_convoy_starts(nodes, 100, 300, 5, 20) == [[100, 220]]


def test_convoy_range_aligned_endpoint_is_half_open():
    # 末车须严格早于 depart_to：首车可行范围 [depart_from, depart_to-h)。
    node = it(cycle=60, green_start=0, green_end=0, travel=0)
    assert compute_convoy_starts([node], 0, 100, 3, 10) == [[0, 80]]
    assert compute_convoy_starts([node], 0, 20, 2, 10) == [[0, 10]]


def test_convoy_span_equal_to_range_length_yields_empty():
    # (vehicle_count-1)*headway == 范围长度时首车范围为空（算法层防御）。
    node = it(cycle=60, green_start=0, green_end=0, travel=0)
    assert compute_convoy_starts([node], 0, 20, 3, 10) == []


def test_convoy_brute_force_equivalence_on_random_cases():
    """与逐秒判定的参考实现完全一致（测试本身才允许逐秒）。"""
    random.seed(20240924)

    def single_feasible(node, t):
        """整数出发时刻 t 在任意实数行驶时间下是否对该路口可行。"""
        tmax = node.get("travel_max", node["travel"])
        arrive_lo = t + node["travel"] + node["offset"]
        arrive_hi = t + tmax + node["offset"]
        gs, ge, c = node["green_start"], node["green_end"], node["cycle"]
        if gs == ge:
            return True
        for q in range(arrive_lo // c - 2, arrive_lo // c + 4):
            if gs < ge:
                a, b = q * c + gs, q * c + ge
            else:  # 跨零点：连续分量 [qC+gs, (q+1)C+ge)
                a, b = q * c + gs, (q + 1) * c + ge
            if a <= arrive_lo and arrive_hi < b:
                return True
        return False

    def brute(nodes, lo, hi, n_vehicles, headway):
        span = (n_vehicles - 1) * headway
        if span >= hi - lo:
            return []
        expected = []
        run_start = None
        for t in range(lo, hi - span + 1):
            ok = t < hi - span
            if ok:
                for j in range(n_vehicles):
                    if any(
                        not single_feasible(node, t + j * headway)
                        for node in nodes
                    ):
                        ok = False
                        break
            if ok:
                if run_start is None:
                    run_start = t
            elif run_start is not None:
                expected.append([run_start, t])
                run_start = None
        if run_start is not None:
            expected.append([run_start, hi - span])
        return expected

    for _ in range(400):
        n_nodes = random.randint(1, 5)
        nodes = []
        for _ in range(n_nodes):
            c = random.randint(1, 60)
            gs = random.randint(0, c - 1)
            ge = random.randint(0, c - 1)
            travel = random.randint(0, 80)
            kwargs = dict(
                cycle=c,
                offset=random.randint(0, c - 1),
                green_start=gs,
                green_end=ge,
                travel=travel,
            )
            if random.random() < 0.5:
                kwargs["travel_max"] = travel + random.randint(0, 20)
            nodes.append(it(**kwargs))
        length = random.randint(2, 400)
        lo = random.randint(0, 200)
        hi = lo + length
        vehicle_count = random.randint(2, 6)
        headway = random.randint(1, 40)
        got = compute_convoy_starts(nodes, lo, hi, vehicle_count, headway)
        assert got == brute(nodes, lo, hi, vehicle_count, headway)
