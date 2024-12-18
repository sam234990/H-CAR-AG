import sys
import os

# 添加 src 文件夹到 sys.path
src_path = "/home/wangshu/rag/hier_graph_rag"
sys.path.append(os.path.abspath(src_path))
# os.environ["WANDB_MODE"] = "offline"
# 设置代理
os.environ["http_proxy"] = "http://127.0.0.1:7892"
os.environ["https_proxy"] = "http://127.0.0.1:7892"


from src.llm import llm_invoker
from src.evaluate.evaluate import *
import multiprocessing as mp
import pandas as pd
import numpy as np
import argparse
import wandb


def process_worker(dataset_part: pd.DataFrame, process_id, prompt, llm_invoker_args):
    results = []
    all_token = 0
    for i in range(len(dataset_part)):
        data = dataset_part.iloc[i]
        query_content = data["question"] + prompt
        llm_res, token = llm_invoker(query_content, args=llm_invoker_args)
        all_token += token
        tmp_res = {
            "id": data["id"],
            "question": data["question"],
            "label": data["label"],
            "pred": llm_res,
        }
        results.append(tmp_res)
        if i % (len(dataset_part) / 3) == 0:
            print(f"Process {process_id}: Processing {i}/{len(dataset_part)}")

    return results, all_token


def run_zero_cot_llm(
    dataset: pd.DataFrame, strategy, save_dir, args=None, num_workers=12
):
    if args.debug_flag:
        dataset = dataset.iloc[:20]
    print(f"Running {strategy} strategy")

    wandb.init(
        project=f"{args.project}",
        name=f"{args.dataset_name}_{args.strategy}_{args.engine}",
        config=args,
    )

    if strategy == "zero-shot":
        prompt = " \n Answer: "
    elif strategy == "cot":
        prompt = "Let’s think step by step. \n Answer: "

    dataset_parts = np.array_split(dataset, num_workers)
    print(f"dataset size: {len(dataset)}")
    print(f"split the dataset into {num_workers} subsets")
    print(f"subset size: {len(dataset_parts[0])}")

    llm_args = Args()
    llm_args.engine = args.engine
    print(f"llm engine: {llm_args.engine}")

    with mp.Pool(processes=num_workers) as pool:
        results = pool.starmap(
            process_worker,
            [
                (dataset_part, idx, prompt, llm_args)
                for idx, dataset_part in enumerate(dataset_parts)
            ],
        )

    # 整理返回结果和token使用量
    flattened_results = [item for sublist, _ in results for item in sublist]
    total_tokens = sum(token for _, token in results)
    results_df = pd.DataFrame(flattened_results)

    print(f"Total tokens used: {total_tokens}")

    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{strategy}_{args.engine}.csv")

    print(f"Saving results to {save_path}")

    results_df.to_csv(save_path, index=False)
    eval_res(save_path=save_path, eval_mode=args.eval_mode, args=args)


def eval_res(save_path, eval_mode, args=None):
    if eval_mode == "KGQA":
        hit = get_accuracy_webqsp_qa(save_path)
        print(f"Test Hit : {hit}")
        wandb.log({"Test Hit": hit})
    elif eval_mode == "DocQA":
        if args.dataset_name != "narrativeqa":
            hit = get_accuracy_doc_qa(save_path)
            print(f"Test Hit : {hit}")
            wandb.log({"Test Hit": hit})
        else:
            Blue_1 = get_bleu_doc_qa(save_path)
            print(f"Test Blue_1 : {Blue_1}")
            wandb.log({"Test Blue_1": Blue_1})


class Args:
    def __init__(self):
        self.api_key = "ollama"
        self.api_base = "http://localhost:5000/forward"
        self.engine = "llama3.1:8b4k"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--project", type=str, default="hcarag")

    parser.add_argument(
        "--dataset_name",
        type=str,
        choices=dataset_name_path.keys(),  # 只允许选择这两个数据集
        default="narrativeqa",
        help=f"Select the dataset name. Options are: {' '.join(dataset_name_path.keys())}",
    )

    parser.add_argument(
        "--strategy",
        type=str,
        default="zero-shot",
    )

    parser.add_argument(
        "--eval_mode",
        type=str,
        choices=["KGQA", "DocQA"],
        default="DocQA",
        help="Evaluation mode for the dataset:['KGQA', 'DocQA']",
    )

    parser.add_argument(
        "--num_workers",
        type=int,
        default=28,
        help="Number of workers for multiprocessing",
    )

    parser.add_argument(
        "--debug_flag",
        type=lambda x: x.lower() == "true",
        default=False,
        help="Debug flag for testing",
    )

    parser.add_argument(
        "--engine",
        type=str,
        default="llama3.1:8b4k",
        help="Engine name for LLM",
    )

    args = parser.parse_args()

    strategy = args.strategy
    dataset_path = dataset_name_path[args.dataset_name]
    save_dir = baseline_save_path_dict[args.dataset_name]

    # Read dataset
    dataset = pd.read_json(dataset_path, lines=True, orient="records")
    # dataset.rename(columns={"answers": "label"}, inplace=True)
    dataset["id"] = range(len(dataset))

    run_zero_cot_llm(
        dataset, strategy, save_dir=save_dir, args=args, num_workers=args.num_workers
    )
