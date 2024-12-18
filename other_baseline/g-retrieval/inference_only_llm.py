import os
import torch
import gc
from tqdm import tqdm
import pandas as pd
from src.config import parse_args_llama
from src.dataset import load_dataset, dataset_output_dir
from src.utils.evaluate import get_accuracy_webqsp
import multiprocessing as mp
from torch.utils.data import Subset
from src.llm import llm_invoker
import tiktoken


def num_tokens(text: str, token_encoder: tiktoken.Encoding | None = None) -> int:
    """Return the number of tokens in the given text."""
    if token_encoder is None:
        token_encoder = tiktoken.get_encoding("cl100k_base")
    return len(token_encoder.encode(text))  # type: ignore


def truncate_to_n_tokens(
    text: str, max_tokens: int, token_encoder: tiktoken.Encoding | None = None
) -> str:
    """Return the first `max_tokens` tokens from the given text using binary search."""
    if token_encoder is None:
        token_encoder = tiktoken.get_encoding("cl100k_base")

    tokens = token_encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text

    # Binary search to find the appropriate cut-off point
    low, high = 0, len(text)
    while low < high:
        mid = (low + high) // 2
        if num_tokens(text[:mid], token_encoder) <= max_tokens:
            low = mid + 1
        else:
            high = mid

    return text[:high]


def process_worker(dataset_part, llm_invoker_args):
    results = []
    all_tokens = 0
    for i, data in enumerate(dataset_part):
        # Truncate data["desc"] to the first 512 tokens
        truncated_desc = truncate_to_n_tokens(data["desc"], 512)
        query_content = data["question"] + truncated_desc
        llm_res, cur_token = llm_invoker(
            query_content,
            args=llm_invoker_args,
            temperature=llm_invoker_args.temperature,
        )
        all_tokens += cur_token
        tmp_res = {
            "id": data["id"],
            "question": data["question"],
            "label": data["label"],
            "pred": llm_res.lower(),
        }
        results.append(tmp_res)
        if i % (len(dataset_part) / 3) == 0:
            print(f"Processing {i}/{len(dataset_part)}")

    return results, all_tokens


def main(args):
    dataset_name = args.dataset
    dataset = load_dataset[dataset_name]()
    # Step 2: 并行处理设置
    num_workers = 20  # 设定并行的进程数量

    # 将数据集拆分为多个子集，每个进程处理一个子集
    dataset_size = len(dataset)
    indices = list(range(dataset_size))
    split_size = dataset_size // num_workers

    # 生成数据子集
    subsets = [
        Subset(dataset, indices[i * split_size : (i + 1) * split_size])
        for i in range(num_workers)
    ]
    print(f"split the dataset into {num_workers} subsets")
    print(f"subset size: {split_size}")

    # 创建llm_invoker_args实例
    llm_invoker_args = Args()
    llm_invoker_args.temperature = args.temperature
    print(f"llm_invoker_args: {llm_invoker_args}")

    # Step 3: 使用进程池并行处理
    with mp.Pool(processes=num_workers) as pool:
        # 将每个子集分配给不同的进程
        results = pool.starmap(
            process_worker, [(subset, llm_invoker_args) for subset in subsets]
        )

    # 合并所有进程的返回结果
    all_results = []
    all_tokens = 0
    for sublist, cur_token in results:
        all_tokens += cur_token
        all_results.extend(sublist)
    all_results_df = pd.DataFrame(all_results)

    # Step 4. Evaluating
    # output_dir =
    output_dir = dataset_output_dir[dataset_name]
    os.makedirs(f"{output_dir}/{dataset_name}", exist_ok=True)
    path = f"{output_dir}/{dataset_name}/model_name_{args.temperature}.csv"
    print(f"path: {path}")

    all_results_df.to_csv(path, index=False)

    # Step 5. Post-processing & Evaluating
    acc = get_accuracy_webqsp(path)
    print(f"Test Acc {acc}")


class Args:
    def __init__(self):
        self.api_key = "ollama"
        self.api_base = "http://localhost:5000/forward"
        self.engine = "llama3.1:8b4k"
        self.temperature = 0.1


if __name__ == "__main__":

    args = parse_args_llama()

    main(args)
    torch.cuda.empty_cache()
    torch.cuda.reset_max_memory_allocated()
    gc.collect()
