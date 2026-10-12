// Brain-SSD native inference integrity probe.
// Builds against PINNED llama.cpp; never modifies the model or upstream loader.
// Standalone CPU-only tool: deterministic greedy token IDs and prompt logits.
#include "llama.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;
static double elapsed_ms(Clock::time_point start, Clock::time_point end) {
    return std::chrono::duration<double, std::milli>(end - start).count();
}

struct Config {
    std::string model;
    std::string prompt = "Quanto e 19 mais 23? Responda somente com o resultado.";
    int context = 512;
    int threads = 4;
    int predict = 16;
    llama_load_mode load_mode = LLAMA_LOAD_MODE_MMAP;
    llama_lazy_mode lazy_mode = LLAMA_LAZY_MODE_OFF;
};

static const char * lazy_mode_name(llama_lazy_mode mode) {
    switch (mode) {
        case LLAMA_LAZY_MODE_OFF:  return "off";
        case LLAMA_LAZY_MODE_AUTO: return "auto";
        case LLAMA_LAZY_MODE_ON:   return "on";
    }
    return "unknown";
}

static int bounded_int(const std::string & text, int lo, int hi) {
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos) {
        throw std::invalid_argument("Expected positive decimal integer");
    }
    auto value = std::stoll(text);
    if (value < lo || value > hi) {
        throw std::invalid_argument("Numeric argument outside the allowed range");
    }
    return static_cast<int>(value);
}

static Config parse(int argc, char ** argv) {
    Config opt;
    for (int i = 1; i < argc; ++i) {
        const std::string flag = argv[i];
        if (i + 1 >= argc) {
            throw std::invalid_argument("Option requires a value: " + flag);
        }
        const std::string value = argv[++i];
        if (flag == "--model") opt.model = value;
        else if (flag == "--prompt") opt.prompt = value;
        else if (flag == "--context") opt.context = bounded_int(value, 32, 8192);
        else if (flag == "--threads") opt.threads = bounded_int(value, 1, 32);
        else if (flag == "--predict") opt.predict = bounded_int(value, 1, 128);
        else if (flag == "--load-mode") {
            if (value == "mmap") opt.load_mode = LLAMA_LOAD_MODE_MMAP;
            else if (value == "none") opt.load_mode = LLAMA_LOAD_MODE_NONE;
            else throw std::invalid_argument("load-mode must be mmap or none");
        } else if (flag == "--lazy-mode") {
            if (value == "off") opt.lazy_mode = LLAMA_LAZY_MODE_OFF;
            else if (value == "auto") opt.lazy_mode = LLAMA_LAZY_MODE_AUTO;
            else if (value == "on") opt.lazy_mode = LLAMA_LAZY_MODE_ON;
            else throw std::invalid_argument("lazy-mode must be off, auto or on");
        } else throw std::invalid_argument("Unknown argument: " + flag);
    }
    if (opt.model.empty() || opt.prompt.empty() || opt.prompt.size() > 2048) {
        throw std::invalid_argument("Provide --model and prompt of 1..2048 bytes");
    }
    return opt;
}

static void batch_set(llama_batch_ext * batch, const llama_token * ids,
                      int count, llama_pos begin) {
    llama_batch_ext_clear(batch);
    for (int i = 0; i < count; ++i) {
        const int idx = llama_batch_ext_add_token(batch, 0, ids[i]);
        if (idx < 0) throw std::runtime_error("Unable to append token to batch");
        const llama_pos position = begin + i;
        llama_batch_ext_set_pos(batch, idx, &position);
    }
    llama_batch_ext_set_output_logits(batch, count - 1, true);
}

static uint64_t logits_digest(const float * logits, int vocab_count) {
    // FNV-1a over IEEE float32 bytes, for exact comparisons on the same build.
    uint64_t hash = UINT64_C(14695981039346656037);
    for (int i = 0; i < vocab_count; ++i) {
        uint32_t bits = 0;
        std::memcpy(&bits, &logits[i], sizeof(bits));
        for (int k = 0; k < 4; ++k) {
            hash ^= (bits >> (8 * k)) & 0xffu;
            hash *= UINT64_C(1099511628211);
        }
    }
    return hash;
}

static void report(const Config & opt, const std::vector<llama_token> & tokens,
                   double load_ms, double prompt_ms, double ttft_ms,
                   double generation_ms, int vocab_count, uint64_t hash,
                   const std::vector<std::pair<int,float>> & top,
                   bool stopped_at_eog) {
    std::ostringstream out;
    out << std::fixed << std::setprecision(6);
    out << "{\"schema\":1,\"type\":\"native_llama_logits_probe\","
        << "\"status\":\"measured\","
        << "\"load_mode\":\"" << (opt.load_mode == LLAMA_LOAD_MODE_MMAP ? "mmap" : "none") << "\","
        << "\"lazy_mode\":\"" << lazy_mode_name(opt.lazy_mode) << "\","
        << "\"context\":" << opt.context << ","
        << "\"threads\":" << opt.threads << ","
        << "\"predict_limit\":" << opt.predict << ","
        << "\"sampling\":\"greedy\","
        << "\"vocab_count\":" << vocab_count << ","
        << "\"model_load_ms\":" << load_ms << ","
        << "\"prompt_eval_ms\":" << prompt_ms << ","
        << "\"first_token_elapsed_ms\":" << ttft_ms << ","
        << "\"generation_elapsed_ms\":" << generation_ms << ","
        << "\"prompt_logits_fnv64\":\"" << std::hex << std::setfill('0')
        << std::setw(16) << hash << std::dec << "\","
        << "\"prompt_top8_logits\":[";
    for (size_t i = 0; i < top.size(); ++i) {
        if (i) out << ",";
        out << "{\"token\":" << top[i].first << ",\"value\":" << top[i].second << "}";
    }
    out << "],\"tokens\":[";
    for (size_t i = 0; i < tokens.size(); ++i) {
        if (i) out << ",";
        out << tokens[i];
    }
    out << "],\"stopped_at_eog\":" << (stopped_at_eog ? "true" : "false")
        << ",\"limitations\":\"Measures API-level logits and first greedy token; "
        << "does not modify GGML weight loading or prove Brain-SSD memory savings.\"}";
    std::cout << out.str() << std::endl;
}

int main(int argc, char ** argv) {
    try {
        const Config options = parse(argc, argv);
        const auto start = Clock::now();
        llama_backend_init();
        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = 0;
        model_params.load_mode = options.load_mode;
        model_params.lazy_mode = options.lazy_mode;
        llama_model * model = llama_model_load_from_file(options.model.c_str(), model_params);
        if (!model) throw std::runtime_error("Model failed to load");
        const auto loaded = Clock::now();
        if (llama_model_has_encoder(model)) throw std::runtime_error("Decoder-only GGUF required");

        const llama_vocab * vocab = llama_model_get_vocab(model);
        const int count = llama_tokenize(vocab, options.prompt.c_str(),
                                         options.prompt.size(), nullptr, 0, true, true);
        if (count >= 0 || -count > options.context - options.predict) {
            throw std::runtime_error("Tokenized prompt exceeds fixed context budget");
        }
        const int n_prompt = -count;
        std::vector<llama_token> prompt(n_prompt);
        if (llama_tokenize(vocab, options.prompt.c_str(), options.prompt.size(),
                           prompt.data(), n_prompt, true, true) != n_prompt) {
            throw std::runtime_error("Tokenization failed");
        }
        llama_context_params ctxp = llama_context_default_params();
        ctxp.n_ctx = static_cast<uint32_t>(options.context);
        ctxp.n_batch = static_cast<uint32_t>(n_prompt);
        ctxp.n_threads = options.threads;
        ctxp.n_threads_batch = options.threads;
        ctxp.no_perf = true;
        llama_context * ctx = llama_init_from_model(model, ctxp);
        if (!ctx) throw std::runtime_error("Context allocation failed");
        llama_batch_ext * batch = llama_batch_ext_init(ctx);
        if (!batch) throw std::runtime_error("Batch allocation failed");
        llama_sampler * sampler = llama_sampler_init_greedy();
        if (!sampler) throw std::runtime_error("Sampler init failed");

        batch_set(batch, prompt.data(), n_prompt, 0);
        if (llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch)) {
            throw std::runtime_error("Prompt evaluation failed");
        }
        const auto evaluated = Clock::now();
        const int vocab_count = llama_vocab_n_tokens(vocab);
        const float * logits = llama_get_logits_ith(ctx, -1);
        if (!logits || vocab_count < 1) throw std::runtime_error("Prompt logits missing");

        const uint64_t checksum = logits_digest(logits, vocab_count);
        std::vector<int> indices(vocab_count);
        for (int i = 0; i < vocab_count; ++i) indices[i] = i;
        const int selected = std::min(8, vocab_count);
        std::partial_sort(indices.begin(), indices.begin() + selected, indices.end(),
            [logits](int a, int b) {
                const float va = std::isnan(logits[a]) ? -std::numeric_limits<float>::infinity() : logits[a];
                const float vb = std::isnan(logits[b]) ? -std::numeric_limits<float>::infinity() : logits[b];
                return va == vb ? a < b : va > vb;
            });
        std::vector<std::pair<int, float>> top;
        for (int k = 0; k < selected; ++k) top.emplace_back(indices[k], logits[indices[k]]);
        const llama_token first = llama_sampler_sample(sampler, ctx, -1);
        const auto first_time = Clock::now();
        std::vector<llama_token> tokens;
        tokens.reserve(options.predict);
        bool stopped = llama_vocab_is_eog(vocab, first);
        if (!stopped) tokens.push_back(first);

        for (int i = 1; i < options.predict && !stopped; ++i) {
            batch_set(batch, &tokens.back(), 1, n_prompt + i - 1);
            if (llama_process(ctx, LLAMA_PROCESS_TYPE_DECODE, batch)) {
                throw std::runtime_error("Generation evaluation failed");
            }
            const llama_token next = llama_sampler_sample(sampler, ctx, -1);
            stopped = llama_vocab_is_eog(vocab, next);
            if (!stopped) tokens.push_back(next);
        }
        const auto finished = Clock::now();
        // Log timing includes model load and prompt eval; it is NOT CLI TTFT.
        report(options, tokens, elapsed_ms(start, loaded), elapsed_ms(loaded, evaluated),
               elapsed_ms(start, first_time), elapsed_ms(evaluated, finished),
               vocab_count, checksum, top, stopped);
        llama_sampler_free(sampler);
        llama_batch_ext_free(batch);
        llama_free(ctx);
        llama_model_free(model);
        llama_backend_free();
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "Brain-SSD native probe failed: " << error.what() << "\n";
        return 2;
    }
}
