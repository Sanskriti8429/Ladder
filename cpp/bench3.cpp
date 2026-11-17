#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "fastbook2.hpp"
#include "orderbook.hpp"

struct Event {
    int op;
    int64_t id;
    int side;
    int64_t price;
    int64_t qty;
};

using Clock = std::chrono::steady_clock;

constexpr uint64_t PRIME = 1099511628211ULL;
constexpr uint64_t BASIS = 14695981039346656037ULL;

static uint64_t g_sink = 0;

static inline uint64_t mix(uint64_t h, uint64_t v) { return (h ^ v) * PRIME; }

static std::vector<Event> load(const char* path) {
    std::ifstream in(path);
    std::string line;
    std::getline(in, line);
    std::vector<Event> events;
    while (std::getline(in, line)) {
        int op, side;
        long long id, price, qty;
        if (std::sscanf(line.c_str(), "%d,%lld,%d,%lld,%lld", &op, &id, &side, &price, &qty) == 5) {
            events.push_back({op, id, side, price, qty});
        }
    }
    return events;
}

struct OriginalRun {
    OrderBook b;
    std::vector<Fill> out;
    void limit(const Event& e) { out = b.add_limit(e.id, e.side == 0, e.price, e.qty); }
    void market(const Event& e) { out = b.market_order(e.side == 0, e.qty); }
    bool cancel(const Event& e) { return b.cancel(e.id); }
    size_t resting() const { return b.resting(); }
    int64_t best_bid() const { return b.best_bid(); }
    int64_t best_ask() const { return b.best_ask(); }
};

template <bool FLAT, bool REUSE>
struct PooledRun {
    PooledBook<FLAT> b;
    std::vector<Fill> out;
    void limit(const Event& e) {
        if constexpr (REUSE) {
            out.clear();
        } else {
            out = std::vector<Fill>();
        }
        b.add_limit(e.id, e.side == 0, e.price, e.qty, out);
    }
    void market(const Event& e) {
        if constexpr (REUSE) {
            out.clear();
        } else {
            out = std::vector<Fill>();
        }
        b.market_order(e.side == 0, e.qty, out);
    }
    bool cancel(const Event& e) { return b.cancel(e.id); }
    size_t resting() const { return b.resting(); }
    int64_t best_bid() const { return b.best_bid(); }
    int64_t best_ask() const { return b.best_ask(); }
};

template <class B>
static void run(const char* name, const std::vector<Event>& events) {
    const size_t n = events.size();
    std::vector<double> times;
    for (int r = 0; r < 7; ++r) {
        B b;
        uint64_t sink = 0;
        auto t0 = Clock::now();
        for (const Event& e : events) {
            if (e.op == 2) {
                sink += b.cancel(e);
            } else {
                if (e.op == 0) {
                    b.limit(e);
                } else {
                    b.market(e);
                }
                sink += b.out.size();
            }
        }
        times.push_back(std::chrono::duration<double>(Clock::now() - t0).count());
        g_sink += sink;
    }
    std::sort(times.begin(), times.end());
    std::printf("\n%s\n", name);
    std::printf("  best of 7: %.4f s (%.1f M events per second)   median of 7: %.4f s   slowest: %.4f s\n",
                times.front(), n / times.front() / 1e6, times[3], times.back());

    std::vector<int64_t> lat[3];
    for (auto& v : lat) v.reserve(n);
    {
        B b;
        for (const Event& e : events) {
            auto t0 = Clock::now();
            if (e.op == 2) {
                b.cancel(e);
            } else if (e.op == 0) {
                b.limit(e);
            } else {
                b.market(e);
            }
            auto t1 = Clock::now();
            lat[e.op].push_back(std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count());
        }
    }
    double med[3];
    for (int k = 0; k < 3; ++k) {
        std::nth_element(lat[k].begin(), lat[k].begin() + lat[k].size() / 2, lat[k].end());
        med[k] = lat[k][lat[k].size() / 2] / 1000.0;
    }
    std::printf("  median latency (us, each includes about 0.0145 of clock): limit %.3f  market %.3f  cancel %.3f\n",
                med[0], med[1], med[2]);

    B b;
    uint64_t h = BASIS;
    uint64_t fills = 0;
    for (const Event& e : events) {
        if (e.op == 2) {
            h = mix(h, b.cancel(e) ? 1 : 0);
        } else {
            if (e.op == 0) {
                b.limit(e);
            } else {
                b.market(e);
            }
            fills += b.out.size();
            for (const Fill& x : b.out) {
                h = mix(h, static_cast<uint64_t>(x.id));
                h = mix(h, static_cast<uint64_t>(x.price));
                h = mix(h, static_cast<uint64_t>(x.qty));
            }
        }
    }
    std::printf("STATE %zu %lld %lld %llu %016llx\n", b.resting(),
                static_cast<long long>(b.best_bid()), static_cast<long long>(b.best_ask()),
                static_cast<unsigned long long>(fills), static_cast<unsigned long long>(h));
}

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "data/events.csv";
    std::vector<Event> events = load(path);
    std::printf("events: %zu\n", events.size());
    run<OriginalRun>("A  original port (deque levels, returned vectors, hash ids)", events);
    run<PooledRun<false, false>>("B  pooled list, hash ids, fresh fills", events);
    run<PooledRun<true, false>>("C  pooled list, flat ids, fresh fills", events);
    run<PooledRun<false, true>>("D  pooled list, hash ids, reused fills", events);
    run<PooledRun<true, true>>("E  pooled list, flat ids, reused fills", events);
    std::printf("\nsink %llu\n", static_cast<unsigned long long>(g_sink));
    return 0;
}