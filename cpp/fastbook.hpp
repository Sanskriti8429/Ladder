#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <map>
#include <vector>

#include "orderbook.hpp"

class FastBook {
public:
    FastBook() {
        nodes_.reserve(1 << 20);
        slot_.reserve(1 << 20);
    }

    void add_limit(int64_t id, bool buy, int64_t price, int64_t qty, std::vector<Fill>& out) {
        int64_t rest = match(buy, qty, true, price, out);
        if (rest > 0) rest_order(id, buy, price, rest);
    }

    void market_order(bool buy, int64_t qty, std::vector<Fill>& out) {
        match(buy, qty, false, 0, out);
    }

    bool cancel(int64_t id) {
        if (id < 0 || static_cast<size_t>(id) >= slot_.size()) return false;
        int32_t s = slot_[id];
        if (s < 0) return false;
        slot_[id] = -1;
        unlink(s);
        release(s);
        return true;
    }

    size_t resting() const { return count_; }
    int64_t best_bid() const { return bids_.empty() ? -1 : bids_.rbegin()->first; }
    int64_t best_ask() const { return asks_.empty() ? -1 : asks_.begin()->first; }

private:
    struct Node {
        int64_t id;
        int64_t qty;
        int64_t price;
        int32_t prev;
        int32_t next;
        bool buy;
    };

    struct Level {
        int32_t head = -1;
        int32_t tail = -1;
    };

    int32_t acquire() {
        if (free_ >= 0) {
            int32_t s = free_;
            free_ = nodes_[s].next;
            return s;
        }
        nodes_.emplace_back();
        return static_cast<int32_t>(nodes_.size()) - 1;
    }

    void release(int32_t s) {
        nodes_[s].next = free_;
        free_ = s;
        --count_;
    }

    void rest_order(int64_t id, bool buy, int64_t price, int64_t qty) {
        int32_t s = acquire();
        Node& n = nodes_[s];
        n.id = id;
        n.qty = qty;
        n.price = price;
        n.buy = buy;
        n.next = -1;
        Level& lv = (buy ? bids_ : asks_)[price];
        n.prev = lv.tail;
        if (lv.tail >= 0) {
            nodes_[lv.tail].next = s;
        } else {
            lv.head = s;
        }
        lv.tail = s;
        if (static_cast<size_t>(id) >= slot_.size()) slot_.resize(static_cast<size_t>(id) + 1, -1);
        slot_[id] = s;
        ++count_;
    }

    void unlink(int32_t s) {
        Node& n = nodes_[s];
        if (n.prev >= 0) nodes_[n.prev].next = n.next;
        if (n.next >= 0) nodes_[n.next].prev = n.prev;
        if (n.prev < 0 || n.next < 0) {
            auto& side = n.buy ? bids_ : asks_;
            auto it = side.find(n.price);
            if (n.prev < 0) it->second.head = n.next;
            if (n.next < 0) it->second.tail = n.prev;
            if (it->second.head < 0) side.erase(it);
        }
    }

    int64_t match(bool buy, int64_t qty, bool has_limit, int64_t limit, std::vector<Fill>& out) {
        auto& levels = buy ? asks_ : bids_;
        while (qty > 0 && !levels.empty()) {
            auto it = buy ? levels.begin() : std::prev(levels.end());
            if (has_limit && (buy ? it->first > limit : it->first < limit)) break;
            Level& lv = it->second;
            while (lv.head >= 0 && qty > 0) {
                Node& o = nodes_[lv.head];
                int64_t take = std::min(qty, o.qty);
                out.push_back({o.id, it->first, take});
                qty -= take;
                if (take == o.qty) {
                    int32_t s = lv.head;
                    slot_[o.id] = -1;
                    lv.head = o.next;
                    if (lv.head >= 0) {
                        nodes_[lv.head].prev = -1;
                    } else {
                        lv.tail = -1;
                    }
                    release(s);
                } else {
                    o.qty -= take;
                }
            }
            if (lv.head < 0) {
                levels.erase(it);
            } else {
                break;
            }
        }
        return qty;
    }

    std::map<int64_t, Level> bids_;
    std::map<int64_t, Level> asks_;
    std::vector<Node> nodes_;
    std::vector<int32_t> slot_;
    int32_t free_ = -1;
    size_t count_ = 0;
};