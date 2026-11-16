#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

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

static std::vector<Fill> apply(OrderBook& book, const Event& e) {
    if (e.op == 0) return book.add_limit(e.id, e.side == 0, e.price, e.qty);
    return book.market_order(e.side == 0, e.qty);
}

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "data/events.csv";
    std::vector<Event> events = load(path);
    const size_t n = events.size();
    std::printf("events: %zu\n", n);

    {
        OrderBook book;
        uint64_t sink = 0;
        auto t0 = Clock::now();
        for (const Event& e : events) {
            if (e.op == 2) {
                sink += book.cancel(e.id);
            } else {
                sink += apply(book, e).size();
            }
        }
        double secs = std::chrono::duration<double>(Clock::now() - t0).count();
        std::printf("time: %.3f s  throughput: %.0f events per second  mean %.3f us per event  (sink %llu)\n",
                    secs, n / secs, secs / n * 1e6, static_cast<unsigned long long>(sink));
    }

    {
        OrderBook book;
        std::vector<int64_t> lat[3];
        for (auto& v : lat) v.reserve(n);
        for (const Event& e : events) {
            auto t0 = Clock::now();
            if (e.op == 2) {
                book.cancel(e.id);
            } else {
                apply(book, e);
            }
            auto t1 = Clock::now();
            lat[e.op].push_back(std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count());
        }
        const char* names[3] = {"limit order", "market order", "cancel"};
        for (int k = 0; k < 3; ++k) {
            std::vector<int64_t>& v = lat[k];
            std::sort(v.begin(), v.end());
            auto at = [&](double p) { return v[static_cast<size_t>(p / 100.0 * (v.size() - 1))] / 1000.0; };
            std::printf("%-13s count %8zu  median %7.2f us  p99 %8.2f  p99.9 %9.2f  max %10.1f\n",
                        names[k], v.size(), at(50), at(99), at(99.9), v.back() / 1000.0);
        }
    }

    OrderBook book;
    uint64_t h = BASIS;
    uint64_t fills = 0;
    for (const Event& e : events) {
        if (e.op == 2) {
            h = mix(h, book.cancel(e.id) ? 1 : 0);
        } else {
            std::vector<Fill> f = apply(book, e);
            fills += f.size();
            for (const Fill& x : f) {
                h = mix(h, static_cast<uint64_t>(x.id));
                h = mix(h, static_cast<uint64_t>(x.price));
                h = mix(h, static_cast<uint64_t>(x.qty));
            }
        }
    }
    std::printf("%zu %lld %lld %llu %016llx\n", book.resting(),
                static_cast<long long>(book.best_bid()), static_cast<long long>(book.best_ask()),
                static_cast<unsigned long long>(fills), static_cast<unsigned long long>(h));
    return 0;
}