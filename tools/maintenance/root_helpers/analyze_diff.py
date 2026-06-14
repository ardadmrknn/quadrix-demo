import os


def get_file_info(root_dir, exclude_dirs=None):

    if exclude_dirs is None:
        exclude_dirs = []

    file_info = {}

    # Normalize exclude paths to absolute paths
    abs_exclude_dirs = [os.path.abspath(d) for d in exclude_dirs]

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Modify dirnames in-place to skip excluded directories
        dirnames[:] = [
            d
            for d in dirnames
            if os.path.abspath(os.path.join(dirpath, d))
            not in abs_exclude_dirs
            and not d.startswith(".")
            and d != "__pycache__"
        ]

        for f in filenames:
            if f.startswith("."):
                continue

            full_path = os.path.join(dirpath, f)
            rel_path = os.path.relpath(full_path, root_dir)
            try:
                size = os.path.getsize(full_path)
                file_info[rel_path] = size
            except OSError:
                pass  # Skip files we can't read

    return file_info


def format_size(size_bytes):
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def main():
    project_root = os.getcwd()
    comparison_target = os.path.join(project_root, "karşılaştırılacak")

    with open("diff_report.txt", "w", encoding="utf-8") as f:
        def log(msg):
            print(msg)
            f.write(msg + "\n")

        log(f"Analyzing Project Root: {project_root}")
        log(f"Comparing against: {comparison_target}")

        # Exclude the comparison target itself and other common noise
        excludes = [
            comparison_target,
            os.path.join(project_root, ".git"),
            os.path.join(project_root, ".gemini"),
            os.path.join(project_root, "venv"),
            os.path.join(project_root, ".venv"),
            os.path.join(project_root, "__pycache__"),
            os.path.join(project_root, "node_modules"),
        ]

        project_files = get_file_info(project_root, exclude_dirs=excludes)
        target_files = get_file_info(comparison_target)

        project_total = sum(project_files.values())
        target_total = sum(target_files.values())

        log("-" * 50)
        log(f"Project Total Size: {format_size(project_total)}")
        log(f"Target Total Size:  {format_size(target_total)}")
        log(f"Difference:         {format_size(target_total - project_total)}")
        log("-" * 50)

        unique_to_target = set(target_files.keys()) - set(project_files.keys())
        unique_to_project = set(project_files.keys()) - set(
            target_files.keys()
        )
        common_files = set(target_files.keys()) & set(project_files.keys())

        log(f"Files unique to 'karşılaştırılacak': {len(unique_to_target)}")
        for file in sorted(
            list(unique_to_target),
            key=lambda x: target_files[x],
            reverse=True,
        )[:10]:
            log(f"  + {file} ({format_size(target_files[file])})")

        log("-" * 20)
        log(f"Files unique to Project: {len(unique_to_project)}")
        for file in sorted(
            list(unique_to_project),
            key=lambda x: project_files[x],
            reverse=True,
        )[:10]:
            log(f"  - {file} ({format_size(project_files[file])})")

        log("-" * 20)
        log("Large size discrepancies in common files:")
        diff_common = []
        for file in common_files:
            diff = target_files[file] - project_files[file]
            if abs(diff) > 1024 * 1024:  # > 1MB difference
                diff_common.append((file, diff))

        diff_common.sort(key=lambda x: abs(x[1]), reverse=True)
        for file, diff in diff_common:
            log(
                f"  * {file} (Diff: {format_size(diff)}) -> "
                f"Target: {format_size(target_files[file])} "
                f"vs Project: {format_size(project_files[file])}"
            )


if __name__ == "__main__":
    main()
