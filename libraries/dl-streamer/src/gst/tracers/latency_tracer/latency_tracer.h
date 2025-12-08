/*******************************************************************************
 * Copyright (C) 2023 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include <gst/gst.h>
#include <gst/gsttracer.h>

#ifdef __cplusplus
#include <unordered_map>
#include <unordered_set>
#endif

G_BEGIN_DECLS

#define LATENCY_TRACER_TYPE (latency_tracer_get_type())
#define LATENCY_TRACER(obj) (G_TYPE_CHECK_INSTANCE_CAST((obj), LATENCY_TRACER_TYPE, LatencyTracer))
#define LATENCY_TRACER_CLASS(klass) (G_TYPE_CHECK_CLASS_CAST((klass), LATENCY_TRACER_TYPE, LatencyTracerClass))
#define IS_LATENCY_TRACER(obj) (G_TYPE_CHECK_INSTANCE_TYPE((obj), LATENCY_TRACER_TYPE))
#define IS_LATENCY_TRACER_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE((klass), LATENCY_TRACER_TYPE))
#define LATENCY_TRACER_CAST(obj) ((LatencyTracer *)(obj))

typedef enum {
    LATENCY_TRACER_FLAG_PIPELINE = 1 << 0,
    LATENCY_TRACER_FLAG_ELEMENT = 1 << 1,
} LatencyTracerFlags;

// Element type cache for fast lookups (Optimization #3)
typedef enum {
    ELEMENT_TYPE_SOURCE,    // Element with SOURCE flag set
    ELEMENT_TYPE_SINK,      // Element with SINK flag set
    ELEMENT_TYPE_MIDDLE,    // Element that is neither source nor sink
} ElementType;

struct LatencyTracer {
    GstTracer parent;

    /*< private >*/
    GstElement *pipeline;
    GstElement *sink_element;
    guint frame_count;
    gdouble toal_latency;
    gdouble min;
    gdouble max;
    gdouble interval_total;
    gdouble interval_min;
    gdouble interval_max;
    guint interval_frame_count;
    GstClockTime interval_init_time;
    gint interval;
    GstClockTime first_frame_init_ts;
    LatencyTracerFlags flags;

#ifdef __cplusplus
    // Optimization #3: Cache element types for O(1) lookups instead of repeated flag checks
    std::unordered_map<GstElement*, ElementType> *element_type_cache;
    
    // Optimization #1: Cache pipeline topology (source-to-sink mappings) for O(1) lookups
    // Note: Currently not implemented as the existing code doesn't do complex topology traversals
    // This cache is reserved for future topology-based optimizations
    
    // Optimization #5: Track source elements for metadata addition optimization
    std::unordered_set<GstElement*> *source_elements;
#endif
};

struct LatencyTracerClass {
    GstTracerClass parent_class;
};

G_GNUC_INTERNAL GType latency_tracer_get_type(void);

G_END_DECLS
