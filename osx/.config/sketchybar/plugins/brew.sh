#!/bin/bash

source "$HOME/.config/sketchybar/colors.sh"

update() {
  # Add loading state at the start of update
  if [ "$1" = "updating" ]; then
    sketchybar --set $NAME label="􀖇" icon.color=$YELLOW
    return
  fi

  COUNT=$(brew outdated | wc -l | tr -d ' ')
  COLOR=$RED

  case "$COUNT" in
    [3-5][0-9]) COLOR=$ORANGE
    ;;
    [1-2][0-9]) COLOR=$YELLOW
    ;;
    [1-9]) COLOR=$WHITE
    ;;
    0) COLOR=$GREEN
       COUNT=􀆅
    ;;
  esac

  args=(--set $NAME label=$COUNT icon.color=$COLOR)
  
  # Update popup items
  args+=(--remove '/brew.update.*/')
  
  COUNTER=0
  while read -r package version newversion; do
    update_item=(
      label="$package: $version → $newversion"
      position=popup.brew
      drawing=on
      click_script="brew upgrade $package 2>/dev/null && sketchybar --trigger brew_update"
    )
    
    args+=(--clone brew.update.$COUNTER brew.template \
           --set brew.update.$COUNTER "${update_item[@]}")
    COUNTER=$((COUNTER + 1))
  done <<< "$(brew outdated --verbose | awk '{print $1, $2, $4}')"

  sketchybar -m "${args[@]}" 2>/dev/null
}

popup() {
  sketchybar --set $NAME popup.drawing=$1
}

case "$SENDER" in
  "routine"|"forced"|"brew_update") update
  ;;
  "mouse.entered") popup on
  ;;
  "mouse.exited"|"mouse.exited.global") popup off
  ;;
  "mouse.clicked") 
    if [ "$BUTTON" = "right" ]; then
      # Store package list before starting updates
      PACKAGES=$(brew outdated --verbose | awk '{print $1}')
      COUNT=$(echo "$PACKAGES" | wc -l | tr -d ' ')
      
      update "updating"
      sketchybar --set $NAME label="􀖇 0/$COUNT" icon.color=$YELLOW

      (
        CURRENT=0
        echo "$PACKAGES" | while read -r package; do
          CURRENT=$((CURRENT + 1))
          sketchybar --set $NAME label="􀖇 $CURRENT/$COUNT: $package"
          # Try to upgrade without auto-update and with error handling
          if ! brew upgrade --no-auto-update "$package" 2>/dev/null; then
            # If failed, try with auto-update
            brew update && brew upgrade "$package"
          fi
        done
        # Final update to refresh status
        sketchybar --trigger brew_update
      ) &
    else
      popup toggle
    fi
    ;;
esac
