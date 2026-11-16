#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "fastbook.hpp"
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

struct SlowRun {
    OrderBook b;
    std::vector<Fill> out;
    void limit(const Event& e) { out = b.add_limit(e.id, e.side == 0, e.price, e.qty); }
    void market(const Event& e) { out = b.market_order(e.side == 0, e.qty); }
    bool cancel(const Event& e) { return b.cancel(e.id); }
    size_t resting() const { return b.resting(); }
    int64_t best_bid() const { return b.best_bid(); }
    int64_t best_ask() const { return b.best_ask(); }
};

struct FastRun {
    FastBook b;
    std::vector<Fill> out;
    void limit(const Event& e) {
        out.clear();
        b.add_limit(e.id, e.side == 0, e.price, e.qty, out);
    }
    void market(const Event& e) {
        out.clear();
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
    std::printf("\n%s\n", name);

    double best = 1e18;
    for (int r = 0; r < 5; ++r) {
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
        double secs = std::chrono::duration<double>(Clock::now() - t0).count();
        best = std::min(best, secs);
        std::printf("  run %d: %.4f s  (sink %llu)\n", r + 1, secs, static_cast<unsigned long long>(sink));
    }
    std::printf("  best of 5: %.4f s  %.0f events per second  %.3f us per event\n", best, n / best, best / n * 1e6);

    {
        B b;
        std::vector<int64_t> lat[3];
        for (auto& v : lat) v.reserve(n);
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
        const char* names[3] = {"limit order", "market order", "cancel"};
        for (int k = 0; k < 3; ++k) {
            std::vector<int64_t>& v = lat[k];
            std::sort(v.begin(), v.end());
            auto at = [&](double p) { return v[static_cast<size_t>(p / 100.0 * (v.size() - 1))] / 1000.0; };
            std::printf("  %-13s count %8zu  median %7.3f us  p99 %8.3f  p99.9 %9.3f  max %10.1f\n",
                        names[k], v.size(), at(50), at(99), at(99.9), v.back() / 1000.0);
        }
    }

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

    {
        const int m = 2000000;
        int64_t acc = 0;
        for (int i = 0; i < m; ++i) {
            auto a = Clock::now();
            auto b = Clock::now();
            acc += std::chrono::duration_cast<std::chrono::nanoseconds>(b - a).count();
        }
        std::printf("clock overhead: about %.1f ns per timed measurement (acc %lld)\n",
                    static_cast<double>(acc) / m, static_cast<long long>(acc));
    }

    run<SlowRun>("original port (std::deque levels, returned vectors, unordered_map index)", events);
    run<FastRun>("fast book (linked-list pool, reused fills buffer, flat id index)", events);
    return 0;
}