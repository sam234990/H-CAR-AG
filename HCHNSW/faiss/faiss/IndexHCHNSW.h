/**
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

// -*- c++ -*-

#pragma once

#include <vector>

#include <faiss/IndexFlat.h>
#include <faiss/IndexPQ.h>
#include <faiss/IndexScalarQuantizer.h>
#include <faiss/impl/HNSW.h>
#include <faiss/utils/utils.h>

namespace faiss {

struct IndexHCHNSW;

/** The HNSW index is a normal random-access index with a HNSW
 * link structure built on top */

struct IndexHCHNSW : Index {
    typedef HNSW::storage_idx_t storage_idx_t;

    // the link structure
    HNSW hnsw;

    // the sequential storage
    bool own_fields = false;
    Index* storage = nullptr;

    // When set to false, level 0 in the knn graph is not initialized.
    // This option is used by GpuIndexCagra::copyTo(IndexHCHNSWCagra*)
    // as level 0 knn graph is copied over from the index built by
    // GpuIndexCagra.
    bool init_level0 = true;

    // When set to true, all neighbors in level 0 are filled up
    // to the maximum size allowed (2 * M). This option is used by
    // IndexHHNSWCagra to create a full base layer graph that is
    // used when GpuIndexCagra::copyFrom(IndexHCHNSWCagra*) is invoked.
    bool keep_max_size_level0 = false;

    explicit IndexHCHNSW(int d = 0, int M = 32, MetricType metric = METRIC_L2);
    explicit IndexHCHNSW(Index* storage, int M = 32);

    ~IndexHCHNSW() override;

    void add(idx_t n, const float* x) override;

    /// Trains the storage if needed
    void train(idx_t n, const float* x) override;

    /// entry point for search
    void search(
            idx_t n,
            const float* x,
            idx_t k,
            float* distances,
            idx_t* labels,
            const SearchParameters* params = nullptr) const override;

    void range_search(
            idx_t n,
            const float* x,
            float radius,
            RangeSearchResult* result,
            const SearchParameters* params = nullptr) const override;

    void reconstruct(idx_t key, float* recons) const override;

    void reset() override;

    void shrink_level_0_neighbors(int size);

    /** Perform search only on level 0, given the starting points for
     * each vertex.
     *
     * @param search_type 1:perform one search per nprobe, 2: enqueue
     *                    all entry points
     */
    void search_level_0(
            idx_t n,
            const float* x,
            idx_t k,
            const storage_idx_t* nearest,
            const float* nearest_d,
            float* distances,
            idx_t* labels,
            int nprobe = 1,
            int search_type = 1,
            const SearchParameters* params = nullptr) const;

    /// alternative graph building
    void init_level_0_from_knngraph(int k, const float* D, const idx_t* I);

    /// alternative graph building
    void init_level_0_from_entry_points(
            int npt,
            const storage_idx_t* points,
            const storage_idx_t* nearests);

    // reorder links from nearest to farthest
    void reorder_links();

    void link_singletons();

    void permute_entries(const idx_t* perm);

    DistanceComputer* get_distance_computer() const override;
};

/** Flat index topped with with a HNSW structure to access elements
 *  more efficiently.
 */

struct IndexHCHNSWFlat : IndexHCHNSW {
    IndexHCHNSWFlat();
    IndexHCHNSWFlat(int d, int M, MetricType metric = METRIC_L2);
};

/** PQ index topped with with a HNSW structure to access elements
 *  more efficiently.
 */
struct IndexHCHNSWPQ : IndexHCHNSW {
    IndexHCHNSWPQ();
    IndexHCHNSWPQ(
            int d,
            int pq_m,
            int M,
            int pq_nbits = 8,
            MetricType metric = METRIC_L2);
    void train(idx_t n, const float* x) override;
};

/** SQ index topped with with a HNSW structure to access elements
 *  more efficiently.
 */
struct IndexHCHNSWSQ : IndexHCHNSW {
    IndexHCHNSWSQ();
    IndexHCHNSWSQ(
            int d,
            ScalarQuantizer::QuantizerType qtype,
            int M,
            MetricType metric = METRIC_L2);
};



} // namespace faiss
