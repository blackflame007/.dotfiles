#!/bin/bash

POPUP_CLICK_SCRIPT="sketchybar --set \$NAME popup.drawing=toggle"

brew=(
  icon=􀐛
  label=?
  padding_right=10
  script="$PLUGIN_DIR/brew.sh"
  click_script="$POPUP_CLICK_SCRIPT"
  popup.align=right
  popup.height=35
  update_freq=180
)

brew_template=(
  drawing=off
  background.corner_radius=12
  padding_left=7
  padding_right=7
  icon.background.height=2
  icon.background.y_offset=-12
  position=popup.brew
)

sketchybar --add event brew_update \
           --add item brew right \
           --set brew "${brew[@]}" \
           --subscribe brew brew_update \
                            mouse.entered \
                            mouse.exited \
                            mouse.exited.global \
                            mouse.clicked \
           --add item brew.template popup.brew \
           --set brew.template "${brew_template[@]}"

