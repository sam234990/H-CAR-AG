import json
from typing import cast
from llm import llm_invoker
from prompts import COMMUNITY_REPORT_PROMPT, COMMUNITY_CONTEXT
from utils import *
from attr_cluster import *


def prep_community_report_context(
    level, community_nodes, relationships, sub_communities_summary=None
):
    entity_str = ""
    for _, row in community_nodes.iterrows():
        entity_str += f"{row['human_readable_id']},{row['name']},{row['description']}\n"
    relationships_str = ""
    for _, row in relationships.iterrows():
        relationships_str += f"{row['human_readable_id']},{row['source']},{row['target']},{row['description']}\n"
    # 将生成的字符串插入到上下文中
    context = COMMUNITY_CONTEXT.format(
        entity_df=entity_str, relationship_df=relationships_str
    )

    return context


def extract_community_report(result):
    """
    Extract the fields from result if valid.
    """
    required_fields = [
        ("title", str),
        ("summary", str),
        ("findings", list),
        ("rating", float),
        ("rating_explanation", str),
    ]
    # Validate the result
    if dict_has_keys_with_types(result, required_fields):
        return {
            "title": result["title"],
            "summary": result["summary"],
            "findings": result["findings"],
            "rating": result["rating"],
            "rating_explanation": result["rating_explanation"],
        }, True
    else:
        return {}, False


def dict_has_keys_with_types(d, keys_with_types):
    """Check if dict `d` contains keys with expected types as defined in `keys_with_types`."""
    for key, expected_type in keys_with_types:
        if key not in d or not isinstance(d[key], expected_type):
            return False
    return True


def generate_community_report(community_text, args, community_id, max_generate=3):
    report_prompt = COMMUNITY_REPORT_PROMPT.format(input_text=community_text)
    current_generated = 0
    retries = 0
    success = False
    raw_result = None

    while not success and retries < max_generate:
        raw_result = llm_invoker(
            report_prompt, args, max_tokens=args.max_tokens, json=True
        )
        try:
            output = json.loads(raw_result)

            extract_result, success = extract_community_report(output)
            if success:
                break
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            retries += 1
        except Exception as e:
            print(f"An error occurred: {e}")
            retries += 1

    if success is False:
        print(f"Failed to generate community report for community:{community_id}")

    return raw_result, extract_result


def community_report(results_by_level, args, final_entities, final_relationships):
    level_0 = results_by_level[0]
    for community_id, node_list in level_0.items():
        # print(f"Community {community_id}:")
        # print(f"Nodes:{node_list}")
        community_nodes = final_entities.loc[final_entities["name"].isin(node_list)]
        community_relationships = final_relationships[
            final_relationships["source"].isin(node_list)
        ]
        print(community_nodes.columns)
        print(community_relationships.columns)
        community_text = prep_community_report_context(
            0, community_nodes, community_relationships
        )

        community_report = generate_community_report(community_text, args, community_id)
        print(community_report)


if __name__ == "__main__":
    parser = create_arg_parser()
    args = parser.parse_args()

    graph, final_entities, final_relationships = read_graph_nx(args.base_path)
    cos_graph = compute_distance(graph=graph)
    results_by_level = attribute_hierarchical_clustering(cos_graph, final_entities)
    community_report(results_by_level, args, final_entities, final_relationships)
