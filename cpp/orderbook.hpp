#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <iterator>
#include <map>
#include <unordered_map>
#include <utility>
#include <vector>

struct Order {
    int64_t id;
    int64_t qty;
};

struct Fill {
    int64_t id;
    int64_t price;
    int64_t qty;
};

class OrderBook {
public:
    std::vector<Fill> add_limit(int64_t id, bool buy, int64_t price, int64_t qty) {
        std::vector<Fill> fills;
        int64_t rest = match(buy, qty, true, price, fills);
        if (rest > 0) {
            auto& side = buy ? bids_ : asks_;
            side[price].push_back({id, rest});
            index_[id] = {buy, price};
        }
        return fills;
    }

    std::vector<Fill> market_order(bool buy, int64_t qty) {
        std::vector<Fill> fills;
        match(buy, qty, false, 0, fills);
        return fills;
    }

    bool cancel(int64_t id) {
        auto it = index_.find(id);
        if (it == index_.end()) return false;
        bool buy = it->second.first;
        int64_t price = it->second.second;
        index_.erase(it);
        auto& side = buy ? bids_ : asks_;
        auto level = side.find(price);
        auto& queue = level->second;
        for (auto o = queue.begin(); o != queue.end(); ++o) {
            if (o->id == id) {
                queue.erase(o);
                break;
            }
        }
        if (queue.empty()) side.erase(level);
        return true;
    }

    size_t resting() const { return index_.size(); }
    int64_t best_bid() const { return bids_.empty() ? -1 : bids_.rbegin()->first; }
    int64_t best_ask() const { return asks_.empty() ? -1 : asks_.begin()->first; }

private:
    int64_t consume(std::deque<Order>& queue, int64_t price, int64_t qty, std::vector<Fill>& fills) {
        while (!queue.empty() && qty > 0) {
            Order& o = queue.front();
            int64_t take = std::min(qty, o.qty);
            fills.push_back({o.id, price, take});
            qty -= take;
            if (take == o.qty) {
                index_.erase(o.id);
                queue.pop_front();
            } else {
                o.qty -= take;
            }
        }
        return qty;
    }

    int64_t match(bool buy, int64_t qty, bool has_limit, int64_t limit, std::vector<Fill>& fills) {
        if (buy) {
            auto it = asks_.begin();
            while (it != asks_.end() && qty > 0) {
                if (has_limit && it->first > limit) break;
                qty = consume(it->second, it->first, qty, fills);
                if (it->second.empty()) {
                    it = asks_.erase(it);
                } else {
                    ++it;
                }
            }
        } else {
            while (!bids_.empty() && qty > 0) {
                auto it = std::prev(bids_.end());
                if (has_limit && it->first < limit) break;
                qty = consume(it->second, it->first, qty, fills);
                if (it->second.empty()) {
                    bids_.erase(it);
                } else {
                    break;
                }
            }
        }
        return qty;
    }

    std::map<int64_t, std::deque<Order>> bids_;
    std::map<int64_t, std::deque<Order>> asks_;
    std::unordered_map<int64_t, std::pair<bool, int64_t>> index_;
};