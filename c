#!/usr/bin/env bash

set -u

# Comma-separated extensions to delete.
# Example: "tmp,log,bak"
EXTENSIONS_RAW="tmp,pyc,bak,html,js"

# Set to true to only print matching files without deleting them.
DRY_RUN=false

parse_extensions() {
    local raw="$1"
    local -n result_ref="$2"
    local item
    local ext

    IFS=',' read -r -a items <<< "$raw"

    for item in "${items[@]}"; do
        ext="$(echo "$item" | xargs)"
        ext="${ext#.}"
        ext="${ext,,}"

        if [[ -n "$ext" ]]; then
            result_ref["$ext"]=1
        fi
    done
}


main() {
    local -A extensions_map=()
    local file_ext=""
    local deleted_count=0
    local matched_count=0

    parse_extensions "$EXTENSIONS_RAW" extensions_map

    if [[ "${#extensions_map[@]}" -eq 0 ]]; then
        echo "No extensions provided. Nothing to do."
        exit 0
    fi

    echo "Current directory: $(pwd)"
    echo "Extensions to delete: $EXTENSIONS_RAW"
    echo "Dry run: $DRY_RUN"
    echo

    while IFS= read -r -d '' file; do
        filename="$(basename "$file")"

        if [[ "$filename" != *.* ]]; then
            continue
        fi

        file_ext="${filename##*.}"
        file_ext="${file_ext,,}"

        if [[ -n "${extensions_map[$file_ext]:-}" ]]; then
            ((matched_count++))

            if [[ "$DRY_RUN" == "true" ]]; then
                echo "Would delete: $file"
            else
                if rm -f -- "$file"; then
                    echo "Deleted: $file"
                    ((deleted_count++))
                else
                    echo "Failed to delete: $file" >&2
                fi
            fi
        fi
    done < <(find . -type f -print0)

    echo
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Done. Matched files: $matched_count"
    else
        echo "Done. Deleted files: $deleted_count"
    fi
}

main "$@"