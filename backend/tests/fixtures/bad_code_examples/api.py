"""Kasıtlı kötü kod — birden fazla örüntüyü tek dosyada gösterir.

Bu fixture'ı `python -m analysis.scan tests/fixtures/bad_code_examples` ile tara
ve raporda her örüntünün yakalanıp yakalanmadığını gör.
"""

import json
import time
import requests
from functools import cache, lru_cache


# UNBOUNDED_CACHE — modül-level dict, eviction yok
_user_cache = {}

# GLOBAL_ACCUMULATOR — sürekli büyür
events = []


# HARDCODED_SECRET (regex)
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
# HARDCODED_SECRET (generic hint)
API_KEY = "real-looking-secret-12345"


@cache  # UNBOUNDED_CACHE: @cache sınırsız
def fib(n):  # DEEP_RECURSION ile birlikte (base case yok varsa)
    return fib(n - 1) + fib(n - 2)


def mutable_default(x=[]):  # MUTABLE_DEFAULT_ARG
    x.append(1)
    return x


@app.get("/users")
def list_users():
    # LARGE_PAYLOAD (.all() pagination yok)
    users = User.query.all()
    # OVERFETCH_COLUMNS (sadece email kullanılıyor)
    for u in users:
        print(u.email)
    return users


@app.get("/sync-feed")
def feed():
    # MISSING_TIMEOUT
    r = requests.get("http://example.com/data")
    # UNHANDLED_EXCEPTION (try yok)
    data = json.loads(r.text)
    return data


async def bad_async(req):
    # SYNC_IN_ASYNC
    time.sleep(1)
    # RACE_CONDITION (global mutate, lock yok)
    _user_cache[req] = 1
    events.append(req)


def slow_endpoint(items):
    # O_N_SQUARED
    for a in items:
        for b in items:
            print(a, b)
    # INEFFICIENT_STRING_CONCAT
    s = ""
    for x in items:
        s += "x"
    # LIST_OVER_GENERATOR
    total = sum([x for x in items])
    return s, total


def n1_demo(users):
    for u in users:
        # N1_QUERY (loop içinde DB call)
        posts = Post.query.filter_by(user_id=u.id).all()
        print(posts)


def open_no_with():
    # UNCLOSED_RESOURCE
    f = open("data.txt")
    # LOAD_FULL_FILE
    return f.read()


def shadow_demo():
    # SHADOW_VARIABLE — `list` built-in'i gölgele
    list = [1, 2, 3]
    return list


def repeated_demo(items):
    for _ in items:
        # REPEATED_COMPUTE — aynı invariant çağrı 2 kez
        a = expensive("constant")
        b = expensive("constant")


def filters_lots():
    # MISSING_INDEX_HINT — aynı alan ≥3 kez filtre
    a = User.query.filter_by(email="a").first()
    b = User.query.filter_by(email="b").first()
    c = User.query.filter_by(email="c").first()
    d = User.query.filter_by(email="d").first()


def dead_function():  # DEAD_CODE adayı — bu dosyada çağrılmıyor
    pass


# Yardımcı (kullanılıyor — dead_code FP olmasın)
mutable_default()
list_users
